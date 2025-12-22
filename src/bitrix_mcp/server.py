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
mcp = FastMCP("bitrix24-mcp")

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
        List of matching tasks with id, title, responsibleId, groupId, and status
    """
    client = get_client()

    try:
        tasks = await client.task_list(
            filter={"%TITLE": query},
            limit=limit,
        )
        return [task.to_search_result() for task in tasks]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task search: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task search: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


async def _task_get(id: int) -> dict[str, Any]:
    """Get detailed information about a task by ID.

    Args:
        id: Task ID

    Returns:
        Task details including id, title, description, responsibleId, groupId, etc.
    """
    client = get_client()

    try:
        task = await client.task_get(task_id=id)
        return task.to_detail_result()
    except BitrixConnectionError as e:
        logger.error(f"Connection error during task get: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during task get: {e}")
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


async def _user_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for users by name.

    Args:
        query: User name to search for (partial match supported)
        limit: Maximum number of results (default: 10)

    Returns:
        List of matching users with id, name, and email
    """
    client = get_client()

    try:
        users = await client.user_get(query=query, limit=limit)
        return [user.to_search_result() for user in users]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during user search: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during user search: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")


# Register tools with MCP server using descriptive docstrings
@mcp.tool
async def task_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for tasks by title. Use this to find a task when user provides task name.
    Returns matching tasks with id, title, responsibleId, groupId, and status."""
    return await _task_search(query=query, limit=limit)


@mcp.tool
async def task_get(id: int) -> dict[str, Any]:
    """Get detailed information about a task by ID. Returns title, description,
    assignee, and group. Use this to read task description for analysis."""
    return await _task_get(id=id)


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
async def user_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for users by name. Use this to find a user's ID when you need to assign tasks.
    Returns matching users with id, name, and email."""
    return await _user_search(query=query, limit=limit)
