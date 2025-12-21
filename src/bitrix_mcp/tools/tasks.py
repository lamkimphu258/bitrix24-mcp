"""MCP tools for Bitrix24 task management.

This module provides three tools for the MCP server:
- task_search: Find tasks by title
- task_get: Get detailed task information
- task_create: Create new tasks or subtasks
"""

import logging
from typing import Any

from ..bitrix.client import Bitrix24Client
from ..bitrix.types import BitrixAPIError, BitrixConnectionError

logger = logging.getLogger(__name__)

# Global client instance - initialized by server
_client: Bitrix24Client | None = None


def set_client(client: Bitrix24Client) -> None:
    """Set the Bitrix24 client instance for tools to use."""
    global _client
    _client = client


def get_client() -> Bitrix24Client:
    """Get the Bitrix24 client instance.

    Raises:
        RuntimeError: If client is not initialized
    """
    if _client is None:
        raise RuntimeError("Bitrix24 client not initialized. Call set_client() first.")
    return _client


async def task_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for tasks by title.

    Use this tool to find a task when the user provides a task name.
    The search performs partial matching on task titles.

    Args:
        query: Task title to search for (partial match supported)
        limit: Maximum number of results (default: 10)

    Returns:
        List of matching tasks with id, title, responsibleId, groupId, and status

    Example:
        >>> results = await task_search("welcome email")
        >>> print(results)
        [{"id": 456, "title": "Auto Send welcome email", "responsibleId": 7, ...}]
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


async def task_get(id: int) -> dict[str, Any]:
    """Get detailed information about a task by ID.

    Use this tool to read task description for analysis, and to get
    assignee (responsibleId) and group (groupId) for creating subtasks.

    Args:
        id: Task ID

    Returns:
        Task details including:
        - id: Task ID
        - title: Task title
        - description: Full task description (for AI analysis)
        - responsibleId: Assignee user ID (copy to subtasks)
        - groupId: Workgroup/Scrum ID (copy to subtasks)
        - parentId: Parent task ID if this is a subtask
        - status: Current status (pending, in_progress, completed, etc.)
        - priority: Priority level (low, medium, high)
        - deadline: Deadline if set
        - createdBy: Creator user ID

    Example:
        >>> task = await task_get(456)
        >>> print(task["description"])
        "Any new sign up user, send welcome email."
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


async def task_create(
    title: str,
    responsibleId: int,
    description: str | None = None,
    groupId: int | None = None,
    parentId: int | None = None,
    deadline: str | None = None,
    priority: int | None = None,
) -> dict[str, Any]:
    """Create a new task or subtask.

    Use parentId to create a subtask under an existing task.
    Copy responsibleId and groupId from the parent task to keep
    subtasks in the same Scrum board with the same assignee.

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

    Example:
        >>> # Create subtask under parent task 456
        >>> result = await task_create(
        ...     title="Set up email service",
        ...     description="Configure SMTP or email service",
        ...     responsibleId=7,  # Same as parent
        ...     groupId=5,        # Same as parent
        ...     parentId=456      # Parent task ID
        ... )
        >>> print(result)
        {"id": 457, "title": "Set up email service"}
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

