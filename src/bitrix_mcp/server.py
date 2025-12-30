"""MCP Server for Bitrix24 task planning.

This server provides tools for AI assistants to help developers
plan and break down tasks into subtasks in Bitrix24 Scrum.
"""

import logging
import os
from typing import Any

from fastmcp import FastMCP

from .bitrix.client import Bitrix24Client
from .bitrix.types import BitrixAPIError, BitrixConnectionError

# Configure logging
log_level = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("bitrix24-lkp-mcp")

# Module-level client (lazy initialization)
_client: Bitrix24Client | None = None


def get_client() -> Bitrix24Client:
    """Get the Bitrix24 client instance.

    Creates a new client if not already initialized.

    Returns:
        Bitrix24Client instance

    Raises:
        RuntimeError: If client cannot be initialized
    """
    global _client
    if _client is None:
        try:
            _client = Bitrix24Client()
            logger.info("Bitrix24 client initialized successfully")
        except ValueError as e:
            logger.error(f"Failed to initialize Bitrix24 client: {e}")
            raise RuntimeError(f"Bitrix24 client not initialized: {e}")
    return _client


def set_client(client: Bitrix24Client) -> None:
    """Set the Bitrix24 client instance.

    Used for testing to inject a mock client.

    Args:
        client: Bitrix24Client instance to use
    """
    global _client
    _client = client


# Define tool functions separately so they can be called directly in tests
# and then register them with @mcp.tool decorator


async def _task_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for tasks by title.

    Args:
        query: Task title to search for (partial match supported)
        limit: Maximum number of results (default: 10)

    Returns:
        List of matching tasks with id, title, responsibleId, groupId, parentId, status, and url
    """
    client = get_client()
    base_url = client.get_base_url()

    try:
        tasks = await client.task_list(
            filter={"%TITLE": query},
            limit=limit,
        )
        return [task.to_search_result(base_url=base_url) for task in tasks]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task search: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task search: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _task_get(id: int, includeComments: bool = False) -> dict[str, Any]:
    """Get detailed information about a task by ID.

    Args:
        id: Task ID
        includeComments: If True, include task comments in the response (legacy API)

    Returns:
        Task details including id, title, description, responsibleId, groupId, url, etc.
        If includeComments is True, includes a 'comments' array.
    """
    client = get_client()
    base_url = client.get_base_url()

    try:
        task = await client.task_get(task_id=id)
        result = task.to_detail_result(base_url=base_url)

        if includeComments:
            comments = await client.task_commentitem_getlist(
                task_id=id,
                order={"POST_DATE": "asc"},
            )
            result["comments"] = [c.to_result() for c in comments]

        return result
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task get: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task get: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _task_comment_add(id: int, message: str) -> dict[str, Any]:
    """Add a comment to a task.

    Args:
        id: Task ID
        message: Comment text

    Returns:
        Object containing taskId, commentId, and created flag
    """
    client = get_client()

    try:
        comment_id = await client.task_commentitem_add(task_id=id, message=message)
        return {"taskId": id, "commentId": comment_id, "created": True}
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task comment add: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task comment add: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _task_create(
    title: str,
    responsibleId: int,
    description: str | None = None,
    groupId: int | None = None,
    parentId: int | None = None,
    deadline: str | None = None,
    priority: int | None = None,
) -> dict[str, Any]:
    """Create a new task or subtask.

    Args:
        title: Task title
        responsibleId: User ID of assignee (copy from parent task)
        description: Task description (HTML supported)
        groupId: Workgroup/Scrum ID (copy from parent task)
        parentId: Parent task ID - creates this as a SUBTASK
        deadline: Deadline in ISO 8601 format (optional)
        priority: Priority: 0=Low, 1=Medium, 2=High (optional)

    Returns:
        Created task info with id and title
    """
    client = get_client()

    try:
        task_id = await client.task_add(
            title=title,
            responsible_id=responsibleId,
            description=description,
            group_id=groupId,
            parent_id=parentId,
            deadline=deadline,
            priority=priority,
        )
        return {"id": task_id, "title": title}
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task create: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task create: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


def _normalize_status(status: str) -> str:
    """Normalize a user-provided task status string.

    Args:
        status: Raw status string (e.g., "In Progress", "done")

    Returns:
        Normalized status key (e.g., "in_progress")
    """
    return status.strip().lower().replace("-", "_").replace(" ", "_")


def _map_status_to_code(status: str) -> int:
    """Map a user-friendly status string to Bitrix24 status code.

    Supports common synonyms like "done" and "in progress".

    Args:
        status: Status string provided by user/tool caller

    Returns:
        Bitrix24 status code

    Raises:
        ValueError: If status string is not recognized
    """
    normalized = _normalize_status(status)

    # Canonical map for Bitrix24 status codes.
    base_map: dict[str, int] = {
        "pending": 2,
        "in_progress": 3,
        "supposedly_completed": 4,
        "completed": 5,
        "deferred": 6,
    }

    # Common synonyms / user phrasing.
    synonyms: dict[str, str] = {
        "inprogress": "in_progress",
        "in_progress": "in_progress",
        "doing": "in_progress",
        "started": "in_progress",
        "start": "in_progress",
        "progress": "in_progress",
        "done": "completed",
        "finished": "completed",
        "complete": "completed",
        "completed": "completed",
        "postponed": "deferred",
        "defer": "deferred",
        "deferred": "deferred",
        "todo": "pending",
        "to_do": "pending",
        "new": "pending",
    }

    canonical = synonyms.get(normalized, normalized)
    if canonical in base_map:
        return base_map[canonical]

    raise ValueError(f"Unknown task status: {status}")


async def _task_update(
    id: int,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    status: str | None = None,
    responsibleId: int | None = None,
    accomplices: list[int] | None = None,
    auditors: list[int] | None = None,
    deadline: str | None = None,
    startDatePlan: str | None = None,
    endDatePlan: str | None = None,
    groupId: int | None = None,
    parentId: int | None = None,
    stageId: int | None = None,
) -> dict[str, Any]:
    """Update an existing task.

    Args:
        id: Task ID
        title: New task title
        description: New task description
        priority: Priority: 0=Low, 1=Medium, 2=High
        status: Status string: pending, in_progress, completed, deferred
            (also supports common synonyms like "done")
        responsibleId: Assignee user ID
        accomplices: Participant user IDs
        auditors: Observer user IDs
        deadline: Deadline in ISO 8601 format
        startDatePlan: Planned start date in ISO 8601 format
        endDatePlan: Planned end date in ISO 8601 format
        groupId: Workgroup/Project ID
        parentId: Parent task ID (0 to clear)
        stageId: Kanban stage ID (0 to clear)

    Returns:
        Object containing id and updated flag.
    """
    client = get_client()

    has_any_field = (
        title is not None
        or description is not None
        or priority is not None
        or status is not None
        or responsibleId is not None
        or accomplices is not None
        or auditors is not None
        or deadline is not None
        or startDatePlan is not None
        or endDatePlan is not None
        or groupId is not None
        or parentId is not None
        or stageId is not None
    )

    if not has_any_field:
        raise RuntimeError("At least one field must be provided to update a task.")

    status_code: int | None = None
    if status is not None:
        try:
            status_code = _map_status_to_code(status)
        except ValueError as e:
            raise RuntimeError(str(e))

    try:
        await client.task_update(
            task_id=id,
            title=title,
            description=description,
            priority=priority,
            status=status_code,
            responsible_id=responsibleId,
            accomplices=accomplices,
            auditors=auditors,
            deadline=deadline,
            start_date_plan=startDatePlan,
            end_date_plan=endDatePlan,
            group_id=groupId,
            parent_id=parentId,
            stage_id=stageId,
        )
        return {"id": id, "updated": True}
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task update: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task update: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _user_search(query: str) -> list[dict[str, Any]]:
    """Search for users by name.

    Fetches all users and filters by name client-side.

    Args:
        query: User name to search for (partial match supported)

    Returns:
        List of matching users with id, name, and email
    """
    client = get_client()

    try:
        users = await client.user_get(query=query)
        return [user.to_search_result() for user in users]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during user search: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during user search: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _task_list_by_user(
    responsibleId: int,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List tasks assigned to a specific user.

    Args:
        responsibleId: User ID of the assignee
        status: Optional status filter: "pending", "in_progress", "completed", "deferred"
        limit: Maximum number of results (default: 50)

    Returns:
        List of tasks with id, title, responsibleId, groupId, parentId, status, and url
    """
    client = get_client()
    base_url = client.get_base_url()

    # Build filter
    filter_params: dict[str, Any] = {"RESPONSIBLE_ID": responsibleId}

    # Map status string to Bitrix24 status code
    status_map = {
        "pending": 2,
        "in_progress": 3,
        "supposedly_completed": 4,
        "completed": 5,
        "deferred": 6,
    }

    if status and status in status_map:
        filter_params["STATUS"] = status_map[status]

    try:
        tasks = await client.task_list(filter=filter_params, limit=limit)
        return [task.to_search_result(base_url=base_url) for task in tasks]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task list by user: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task list by user: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _group_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search workgroups/scrums by name.

    Args:
        query: Group name query (substring match)
        limit: Maximum number of results to return

    Returns:
        List of group matches with id, name, description, ownerId, isProject, scrumMasterId.
    """
    client = get_client()

    try:
        groups = await client.group_search(query=query, limit=limit)
        return [group.to_result() for group in groups]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during group search: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during group search: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


# Register tools with MCP server using descriptive docstrings
@mcp.tool
async def task_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for tasks by title. Use this to find a task when user provides task name.
    Returns matching tasks with id, title, responsibleId, groupId, parentId, and status."""
    return await _task_search(query=query, limit=limit)


@mcp.tool
async def task_get(id: int, includeComments: bool = False) -> dict[str, Any]:
    """Get detailed information about a task by ID. Returns title, description,
    assignee, and group. Use this to read task description for analysis.

    Args:
        id: Task ID
        includeComments: If True, include task comments (legacy API) in the response
    """
    return await _task_get(id=id, includeComments=includeComments)


@mcp.tool
async def task_comment_add(id: int, message: str) -> dict[str, Any]:
    """Add a comment to a task. Returns the created commentId."""
    return await _task_comment_add(id=id, message=message)


@mcp.tool
async def task_create(
    title: str,
    responsibleId: int,
    description: str | None = None,
    groupId: int | None = None,
    parentId: int | None = None,
    deadline: str | None = None,
    priority: int | None = None,
) -> dict[str, Any]:
    """Create a new task or subtask. Use parentId to create a subtask under an existing task.
    Copy responsibleId and groupId from parent task."""
    return await _task_create(
        title=title,
        responsibleId=responsibleId,
        description=description,
        groupId=groupId,
        parentId=parentId,
        deadline=deadline,
        priority=priority,
    )


@mcp.tool
async def task_update(
    id: int,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    status: str | None = None,
    responsibleId: int | None = None,
    accomplices: list[int] | None = None,
    auditors: list[int] | None = None,
    deadline: str | None = None,
    startDatePlan: str | None = None,
    endDatePlan: str | None = None,
    groupId: int | None = None,
    parentId: int | None = None,
    stageId: int | None = None,
) -> dict[str, Any]:
    """Update a task.

    Supports updating main fields (title/description/priority/status), people
    (assignee/participants/observers), dates (deadline/planned dates), project linking
    (groupId/parentId), and stageId (Kanban stage).
    """
    return await _task_update(
        id=id,
        title=title,
        description=description,
        priority=priority,
        status=status,
        responsibleId=responsibleId,
        accomplices=accomplices,
        auditors=auditors,
        deadline=deadline,
        startDatePlan=startDatePlan,
        endDatePlan=endDatePlan,
        groupId=groupId,
        parentId=parentId,
        stageId=stageId,
    )


@mcp.tool
async def user_search(query: str) -> list[dict[str, Any]]:
    """Search for users by name. Use this to find a user's ID when you need to assign tasks.
    Returns matching users with id, name, and email."""
    return await _user_search(query=query)


@mcp.tool
async def task_list_by_user(
    responsibleId: int,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List tasks assigned to a specific user. Use after finding user ID with user_search.
    Optional status filter: "pending", "in_progress", "completed", "deferred"."""
    return await _task_list_by_user(
        responsibleId=responsibleId,
        status=status,
        limit=limit,
    )


@mcp.tool
async def group_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for workgroups/scrums by name.

    Use this when the user provides a group name (and does not know the ID).
    Returns matching groups with id, name, description, ownerId, isProject, scrumMasterId.
    """
    return await _group_search(query=query, limit=limit)
