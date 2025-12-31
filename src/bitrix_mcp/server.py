"""MCP Server for Bitrix24 task planning.

This server provides tools for AI assistants to help developers
plan and break down tasks into subtasks in Bitrix24 Scrum.
"""

import logging
import os
from datetime import datetime, timezone
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
    priority: str | None = None,
) -> dict[str, Any]:
    """Create a new task or subtask.

    Args:
        title: Task title
        responsibleId: User ID of assignee (copy from parent task)
        description: Task description (HTML supported)
        groupId: Workgroup/Scrum ID (copy from parent task)
        parentId: Parent task ID - creates this as a SUBTASK
        deadline: Deadline in ISO 8601 format (optional)
        priority: Priority: low, medium, high (optional)

    Returns:
        Created task info with id and title
    """
    client = get_client()

    priority_code: int | None = None
    if priority is not None:
        try:
            priority_code = _map_priority_to_code(priority)
        except ValueError as e:
            raise RuntimeError(str(e))

    try:
        task_id = await client.task_add(
            title=title,
            responsible_id=responsibleId,
            description=description,
            group_id=groupId,
            parent_id=parentId,
            deadline=deadline,
            priority=priority_code,
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


def _normalize_priority(priority: str) -> str:
    """Normalize a user-provided task priority string.

    Args:
        priority: Raw priority string (e.g., "High", "medium", "LOW")

    Returns:
        Normalized priority key (e.g., "high")
    """
    return priority.strip().lower().replace("-", "_").replace(" ", "_")


def _map_priority_to_code(priority: str | int) -> int:
    """Map a user-friendly priority (string or int) to Bitrix24 priority code.

    Args:
        priority: Priority as low/medium/high

    Returns:
        Bitrix24 priority code (0=low, 1=medium, 2=high)

    Raises:
        ValueError: If priority is not recognized
    """
    if not isinstance(priority, str):
        raise ValueError(f"Unknown task priority: {priority}. Use one of: low, medium, high.")

    normalized = _normalize_priority(priority)

    # Common synonyms / user phrasing.
    synonyms: dict[str, int] = {
        "low": 0,
        "medium": 1,
        "med": 1,
        "normal": 1,
        "default": 1,
        "high": 2,
        "urgent": 2,
        "critical": 2,
    }

    if normalized in synonyms:
        return synonyms[normalized]

    raise ValueError(f"Unknown task priority: {priority}. Use one of: low, medium, high.")


async def _task_update(
    id: int,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
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
        priority: Priority: low, medium, high
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

    priority_code: int | None = None
    if priority is not None:
        try:
            priority_code = _map_priority_to_code(priority)
        except ValueError as e:
            raise RuntimeError(str(e))

    try:
        await client.task_update(
            task_id=id,
            title=title,
            description=description,
            priority=priority_code,
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


async def _task_stages_get(entityId: int) -> list[dict[str, Any]]:
    """Get Scrum kanban stages (columns) for the current sprint of a group.

    Args:
        entityId: Scrum group (workgroup/project) ID. If set to 0, returns "My Planner" stages
            for the current user (non-scrum fallback).

    Returns:
        List of stages with id, title, sort, color, systemType, and sprintId.
    """
    client = get_client()

    try:
        # Backward-compatible fallback: entityId=0 lists personal "My Planner" stages.
        if entityId == 0:
            stages = await client.task_kanban_stages_get(entity_id=0)
            results = [stage.to_result() for stage in stages]
            return sorted(
                results,
                key=lambda s: (
                    s.get("sort") is None,
                    s.get("sort") or 0,
                    s.get("id") or 0,
                ),
            )

        # Scrum boards have stages per sprint.
        sprints = await client.scrum_sprint_list(group_id=entityId)
        if not sprints:
            raise RuntimeError(f"No sprints found for groupId={entityId}")

        def _norm(value: str | None) -> str:
            return (value or "").strip().lower()

        current_sprint = next((s for s in sprints if _norm(s.status) == "active"), None)

        if current_sprint is None:
            now = datetime.now(timezone.utc)

            def _parse_iso(dt_str: str | None) -> datetime | None:
                if not dt_str:
                    return None
                try:
                    dt = datetime.fromisoformat(dt_str)
                except ValueError:
                    return None
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)

            in_range: list[tuple[datetime, Any]] = []
            for sprint in sprints:
                date_start = _parse_iso(sprint.date_start)
                date_end = _parse_iso(sprint.date_end)
                if (
                    date_start
                    and date_end
                    and date_start <= now <= date_end
                    and _norm(sprint.status) in {"planned", "active"}
                ):
                    in_range.append((date_start, sprint))

            if in_range:
                in_range.sort(key=lambda x: x[0], reverse=True)
                current_sprint = in_range[0][1]

        if current_sprint is None:
            current_sprint = next(
                (s for s in sprints if _norm(s.status) not in {"completed", "done"}),
                sprints[0],
            )

        stages = await client.scrum_kanban_get_stages(sprint_id=current_sprint.id)
        results = [stage.to_result() for stage in stages]
        return sorted(
            results,
            key=lambda s: (
                s.get("sort") is None,
                s.get("sort") or 0,
                s.get("id") or 0,
            ),
        )
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task stages get: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task stages get: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _task_stages_move_task(
    id: int,
    stageId: int,
    before: int | None = None,
    after: int | None = None,
) -> dict[str, Any]:
    """Move a task between kanban/"My Planner" stages (columns).

    Args:
        id: Task ID
        stageId: Target stage ID
        before: Optional task ID before which the task should be placed in the stage
        after: Optional task ID after which the task should be placed in the stage

    Returns:
        Object containing id, stageId, and moved flag.
    """
    if before is not None and after is not None:
        raise RuntimeError("Parameters 'before' and 'after' are mutually exclusive.")

    client = get_client()

    try:
        moved = await client.task_stages_move_task(
            task_id=id,
            stage_id=stageId,
            before=before,
            after=after,
        )

        result: dict[str, Any] = {"id": id, "stageId": stageId, "moved": moved}
        if before is not None:
            result["before"] = before
        if after is not None:
            result["after"] = after
        return result
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task stage move: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task stage move: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


def _normalize_text(value: str) -> str:
    """Normalize user-provided free-text for matching."""
    return value.strip().lower()


async def _resolve_scrum_epic_by_name(
    *,
    client: Bitrix24Client,
    group_id: int,
    epic_name: str,
) -> tuple[int, str]:
    """Resolve a Scrum epic by name to an epicId within a group.

    Matching behavior:
    - Prefer exact match (case-insensitive)
    - Fallback to substring match
    - Raise if ambiguous or not found
    """
    needle = _normalize_text(epic_name)
    if not needle:
        raise RuntimeError("epicName must be non-empty.")

    exact: list[Any] = []
    partial: list[Any] = []
    seen_ids: set[int] = set()

    start = 0
    select = ["ID", "GROUP_ID", "NAME", "DESCRIPTION", "CREATED_BY", "MODIFIED_BY", "COLOR"]
    while True:
        epics = await client.scrum_epic_list(
            filter={"GROUP_ID": group_id},
            order={"ID": "asc"},
            select=select,
            start=start,
        )
        if not epics:
            break

        for epic in epics:
            if epic.id in seen_ids:
                continue
            seen_ids.add(epic.id)
            name_norm = _normalize_text(epic.name)
            if name_norm == needle:
                exact.append(epic)
                if len(exact) > 1:
                    break
            elif needle in name_norm:
                partial.append(epic)

        if len(exact) > 1:
            break

        # Bitrix24 uses a static page size of 50 for this method; fewer results means we're done.
        if len(epics) < 50:
            break

        start += 50

    if len(exact) == 1:
        epic = exact[0]
        return epic.id, epic.name

    if len(exact) > 1:
        candidates = [{"id": e.id, "name": e.name} for e in exact[:10]]
        raise RuntimeError(
            f"Ambiguous epicName '{epic_name}' (groupId={group_id}). Matches: {candidates}. "
            "Use epicId instead."
        )

    if len(partial) == 1:
        epic = partial[0]
        return epic.id, epic.name

    if len(partial) > 1:
        partial_sorted = sorted(partial, key=lambda e: (len(e.name or ""), e.id))
        candidates = [{"id": e.id, "name": e.name} for e in partial_sorted[:10]]
        raise RuntimeError(
            f"Ambiguous epicName '{epic_name}' (groupId={group_id}). Matches: {candidates}. "
            "Use epicId instead."
        )

    raise RuntimeError(
        f"No epic found for epicName '{epic_name}' in groupId={group_id}. "
        "Use scrum_epic_list to discover epics."
    )


async def _scrum_epic_list(
    groupId: int,
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List Scrum epics for a group (tasks.api.scrum.epic.list).

    Args:
        groupId: Scrum group/workgroup ID.
        query: Optional epic name filter (case-insensitive substring match).
        limit: Maximum number of results to return (default: 50).

    Returns:
        List of epics with id, groupId, name, description, createdBy, modifiedBy, color.
    """
    if limit <= 0:
        return []

    client = get_client()
    needle = _normalize_text(query) if query and query.strip() else None

    start = 0
    collected: list[Any] = []
    seen_ids: set[int] = set()
    select = ["ID", "GROUP_ID", "NAME", "DESCRIPTION", "CREATED_BY", "MODIFIED_BY", "COLOR"]

    try:
        while len(collected) < limit:
            epics = await client.scrum_epic_list(
                filter={"GROUP_ID": groupId},
                order={"ID": "asc"},
                select=select,
                start=start,
            )
            if not epics:
                break

            if needle is None:
                for epic in epics:
                    if epic.id in seen_ids:
                        continue
                    seen_ids.add(epic.id)
                    collected.append(epic)
            else:
                for epic in epics:
                    if epic.id in seen_ids:
                        continue
                    if needle in _normalize_text(epic.name):
                        seen_ids.add(epic.id)
                        collected.append(epic)

            # Bitrix24 uses a static page size of 50; fewer results means we're done.
            if len(epics) < 50:
                break

            start += 50

        if needle is not None:
            collected.sort(
                key=lambda e: (
                    0 if _normalize_text(e.name) == needle else 1,
                    len(e.name or ""),
                    e.id,
                )
            )

        return [e.to_result() for e in collected[:limit]]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during scrum epic list: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during scrum epic list: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _scrum_task_get(id: int) -> dict[str, Any]:
    """Get Scrum-specific fields for a task (tasks.api.scrum.task.get)."""
    client = get_client()
    try:
        scrum_task = await client.scrum_task_get(task_id=id)
        result = scrum_task.to_result()
        result["id"] = id
        return result
    except BitrixConnectionError as e:
        logger.error(f"Connection error during scrum task get: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during scrum task get: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _scrum_task_update(
    id: int,
    epicId: int | None = None,
    epicName: str | None = None,
    storyPoints: str | None = None,
    entityId: int | None = None,
    sort: int | None = None,
) -> dict[str, Any]:
    """Update Scrum fields for an existing task (tasks.api.scrum.task.update).

    Supports setting epic by epicId or resolving by epicName (within the task's groupId).
    """
    if epicId is not None and epicName is not None:
        raise RuntimeError("Parameters 'epicId' and 'epicName' are mutually exclusive.")

    client = get_client()

    resolved_epic_id: int | None = epicId
    resolved_epic_name: str | None = None

    try:
        if epicName is not None:
            task = await client.task_get(task_id=id)
            if not task.group_id:
                raise RuntimeError(
                    "Task is not linked to a groupId; cannot resolve epicName for a non-Scrum task."
                )
            group_id = int(task.group_id)
            resolved_epic_id, resolved_epic_name = await _resolve_scrum_epic_by_name(
                client=client,
                group_id=group_id,
                epic_name=epicName,
            )

        update_result = await client.scrum_task_update(
            task_id=id,
            entity_id=entityId,
            story_points=storyPoints,
            epic_id=resolved_epic_id,
            sort=sort,
        )

        errors = update_result.get("errors")
        updated = True
        if isinstance(errors, list) and errors:
            updated = False

        result: dict[str, Any] = {"id": id, "updated": updated}
        if resolved_epic_id is not None:
            result["epicId"] = resolved_epic_id
        if resolved_epic_name is not None:
            result["epicName"] = resolved_epic_name
        if storyPoints is not None:
            result["storyPoints"] = storyPoints
        if entityId is not None:
            result["entityId"] = entityId
        if sort is not None:
            result["sort"] = sort
        return result
    except BitrixConnectionError as e:
        logger.error(f"Connection error during scrum task update: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during scrum task update: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _scrum_task_create(
    title: str,
    responsibleId: int,
    groupId: int,
    description: str | None = None,
    deadline: str | None = None,
    priority: str | None = None,
    epicId: int | None = None,
    epicName: str | None = None,
    storyPoints: str | None = None,
    entityId: int | None = None,
    sort: int | None = None,
) -> dict[str, Any]:
    """Create a task and attach it to Scrum (epic/story points/backlog/sprint).

    Note:
        This tool creates the underlying task via tasks.task.add, then configures Scrum fields
        via tasks.api.scrum.task.update.
    """
    if epicId is not None and epicName is not None:
        raise RuntimeError("Parameters 'epicId' and 'epicName' are mutually exclusive.")

    client = get_client()

    priority_code: int | None = None
    if priority is not None:
        try:
            priority_code = _map_priority_to_code(priority)
        except ValueError as e:
            raise RuntimeError(str(e))

    resolved_epic_id: int | None = epicId
    resolved_epic_name: str | None = None

    try:
        if epicName is not None:
            resolved_epic_id, resolved_epic_name = await _resolve_scrum_epic_by_name(
                client=client,
                group_id=groupId,
                epic_name=epicName,
            )

        task_id = await client.task_add(
            title=title,
            responsible_id=responsibleId,
            description=description,
            group_id=groupId,
            deadline=deadline,
            priority=priority_code,
        )

        update_result = await client.scrum_task_update(
            task_id=task_id,
            entity_id=entityId,
            story_points=storyPoints,
            epic_id=resolved_epic_id,
            sort=sort,
        )

        errors = update_result.get("errors")
        scrum_updated = True
        if isinstance(errors, list) and errors:
            scrum_updated = False

        result: dict[str, Any] = {
            "id": task_id,
            "title": title,
            "groupId": groupId,
            "created": True,
            "scrumUpdated": scrum_updated,
        }
        if resolved_epic_id is not None:
            result["epicId"] = resolved_epic_id
        if resolved_epic_name is not None:
            result["epicName"] = resolved_epic_name
        if storyPoints is not None:
            result["storyPoints"] = storyPoints
        if entityId is not None:
            result["entityId"] = entityId
        if sort is not None:
            result["sort"] = sort
        return result
    except BitrixConnectionError as e:
        logger.error(f"Connection error during scrum task create: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during scrum task create: {e}")
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
    priority: str | None = None,
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
    priority: str | None = None,
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
async def scrum_epic_list(
    groupId: int,
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List Scrum epics for a group.

    Use this to find an epic by name and obtain its id (epicId) for other Scrum operations.
    """
    return await _scrum_epic_list(groupId=groupId, query=query, limit=limit)


@mcp.tool
async def scrum_task_get(id: int) -> dict[str, Any]:
    """Get Scrum-specific fields for a task (epicId, storyPoints, entityId, etc.)."""
    return await _scrum_task_get(id=id)


@mcp.tool
async def scrum_task_update(
    id: int,
    epicId: int | None = None,
    epicName: str | None = None,
    storyPoints: str | None = None,
    entityId: int | None = None,
    sort: int | None = None,
) -> dict[str, Any]:
    """Update Scrum fields for an existing task.

    If epicName is provided, the tool resolves it within the task's groupId via scrum_epic_list,
    then calls tasks.api.scrum.task.update.
    """
    return await _scrum_task_update(
        id=id,
        epicId=epicId,
        epicName=epicName,
        storyPoints=storyPoints,
        entityId=entityId,
        sort=sort,
    )


@mcp.tool
async def scrum_task_create(
    title: str,
    responsibleId: int,
    groupId: int,
    description: str | None = None,
    deadline: str | None = None,
    priority: str | None = None,
    epicId: int | None = None,
    epicName: str | None = None,
    storyPoints: str | None = None,
    entityId: int | None = None,
    sort: int | None = None,
) -> dict[str, Any]:
    """Create a task and attach Scrum fields (epic/story points/backlog/sprint).

    This tool creates the base task via tasks.task.add, then configures Scrum via
    tasks.api.scrum.task.update.
    """
    return await _scrum_task_create(
        title=title,
        responsibleId=responsibleId,
        groupId=groupId,
        description=description,
        deadline=deadline,
        priority=priority,
        epicId=epicId,
        epicName=epicName,
        storyPoints=storyPoints,
        entityId=entityId,
        sort=sort,
    )


@mcp.tool
async def task_stages_get(entityId: int) -> list[dict[str, Any]]:
    """Get Scrum kanban stages (columns) for the current sprint of a group.

    For Scrum boards, this tool:
    - Calls tasks.api.scrum.sprint.list for the group (entityId)
    - Picks the "active" sprint if present (otherwise a best-effort fallback)
    - Calls tasks.api.scrum.kanban.getStages with that sprintId

    Use entityId=0 to get the current user's "My Planner" columns (non-scrum fallback).
    """
    return await _task_stages_get(entityId=entityId)


@mcp.tool
async def task_stages_move_task(
    id: int, stageId: int, before: int | None = None, after: int | None = None
) -> dict[str, Any]:
    """Move a task between kanban/"My Planner" stages (columns).

    Set `before` or `after` to control the task position within the target column.
    """
    return await _task_stages_move_task(id=id, stageId=stageId, before=before, after=after)


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
