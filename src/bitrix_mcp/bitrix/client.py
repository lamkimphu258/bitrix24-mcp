"""Bitrix24 API client with rate limiting and error handling."""

import asyncio
import logging
import os
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from .types import BitrixAPIError, BitrixConnectionError, BitrixTask, BitrixUser

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for Bitrix24 API (2 requests/second)."""

    def __init__(self, rate: float = 2.0):
        """Initialize rate limiter.

        Args:
            rate: Maximum requests per second (default 2.0 for Bitrix24)
        """
        self.rate = rate
        self.tokens = rate
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class Bitrix24Client:
    """Async HTTP client for Bitrix24 REST API."""

    # Default fields to select for task operations
    TASK_LIST_SELECT = ["ID", "TITLE", "RESPONSIBLE_ID", "GROUP_ID", "STATUS"]
    TASK_GET_SELECT = [
        "ID",
        "TITLE",
        "DESCRIPTION",
        "RESPONSIBLE_ID",
        "GROUP_ID",
        "CREATED_BY",
        "STATUS",
        "DEADLINE",
        "PARENT_ID",
        "PRIORITY",
    ]

    def __init__(self, webhook_url: str | None = None):
        """Initialize Bitrix24 client.

        Args:
            webhook_url: Bitrix24 inbound webhook URL.
                        If not provided, reads from BITRIX_WEBHOOK_URL env var.

        Raises:
            ValueError: If webhook URL is not provided or invalid.
        """
        self.webhook_url = webhook_url or os.getenv("BITRIX_WEBHOOK_URL")

        if not self.webhook_url:
            raise ValueError(
                "Bitrix24 webhook URL is required. "
                "Set BITRIX_WEBHOOK_URL environment variable or pass webhook_url parameter."
            )

        # Ensure webhook URL ends with /
        if not self.webhook_url.endswith("/"):
            self.webhook_url += "/"

        # Validate URL format
        if not self.webhook_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid webhook URL format: {self.webhook_url}")

        self._client = httpx.AsyncClient(timeout=30.0)
        self._rate_limiter = RateLimiter(rate=2.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "Bitrix24Client":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a request to Bitrix24 REST API.

        Args:
            method: API method name (e.g., 'tasks.task.list')
            params: Request parameters

        Returns:
            API response result

        Raises:
            BitrixAPIError: On API error response
            BitrixConnectionError: On connection error
        """
        await self._rate_limiter.acquire()

        url = urljoin(self.webhook_url, method)
        logger.debug(f"Bitrix24 API request: {method} with params: {params}")

        try:
            response = await self._client.post(url, json=params or {})
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise BitrixConnectionError(f"Failed to connect to Bitrix24: {e}")
        except httpx.TimeoutException as e:
            raise BitrixConnectionError(f"Request to Bitrix24 timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise BitrixAPIError(
                f"HTTP error from Bitrix24: {e.response.status_code}",
                error_code=str(e.response.status_code),
            )

        data = response.json()

        # Check for API-level errors
        if "error" in data:
            raise BitrixAPIError(
                f"Bitrix24 API error: {data.get('error_description', data['error'])}",
                error_code=data.get("error"),
                error_description=data.get("error_description"),
            )

        return data.get("result", {})

    async def task_list(
        self,
        filter: dict[str, Any] | None = None,
        select: list[str] | None = None,
        limit: int = 10,
    ) -> list[BitrixTask]:
        """List tasks with optional filtering.

        Args:
            filter: Filter conditions (e.g., {"%TITLE": "search query"})
            select: Fields to return (uses default if not specified)
            limit: Maximum number of results

        Returns:
            List of BitrixTask objects
        """
        params = {
            "filter": filter or {},
            "select": select or self.TASK_LIST_SELECT,
            "limit": limit,
        }

        result = await self._request("tasks.task.list", params)
        tasks_data = result.get("tasks", [])

        return [BitrixTask.model_validate(task) for task in tasks_data]

    async def task_get(
        self,
        task_id: int,
        select: list[str] | None = None,
    ) -> BitrixTask:
        """Get a single task by ID.

        Args:
            task_id: Task ID
            select: Fields to return (uses default if not specified)

        Returns:
            BitrixTask object

        Raises:
            BitrixAPIError: If task not found or other API error
        """
        params = {
            "taskId": task_id,
            "select": select or self.TASK_GET_SELECT,
        }

        result = await self._request("tasks.task.get", params)
        task_data = result.get("task", {})

        if not task_data:
            raise BitrixAPIError(f"Task {task_id} not found", error_code="TASK_NOT_FOUND")

        return BitrixTask.model_validate(task_data)

    async def task_add(
        self,
        title: str,
        responsible_id: int,
        description: str | None = None,
        group_id: int | None = None,
        parent_id: int | None = None,
        deadline: str | None = None,
        priority: int | None = None,
    ) -> int:
        """Create a new task.

        Args:
            title: Task title
            responsible_id: User ID of assignee
            description: Task description (HTML supported)
            group_id: Workgroup/Scrum ID
            parent_id: Parent task ID (creates subtask)
            deadline: Deadline in ISO 8601 format
            priority: Priority (0=Low, 1=Medium, 2=High)

        Returns:
            Created task ID
        """
        fields: dict[str, Any] = {
            "TITLE": title,
            "RESPONSIBLE_ID": responsible_id,
        }

        if description is not None:
            fields["DESCRIPTION"] = description
        if group_id is not None:
            fields["GROUP_ID"] = group_id
        if parent_id is not None:
            fields["PARENT_ID"] = parent_id
        if deadline is not None:
            fields["DEADLINE"] = deadline
        if priority is not None:
            fields["PRIORITY"] = priority

        result = await self._request("tasks.task.add", {"fields": fields})

        # Result contains {"task": {"id": 123}} or {"task": 123}
        task_result = result.get("task", {})
        if isinstance(task_result, dict):
            return int(task_result.get("id", task_result.get("ID", 0)))
        return int(task_result)

    async def user_get(
        self,
        query: str,
        limit: int = 10,
    ) -> list[BitrixUser]:
        """Search for users by name.

        Uses the FIND filter for general search across name, last name, and email.

        Args:
            query: Search query (name, last name, or email)
            limit: Maximum number of results

        Returns:
            List of BitrixUser objects
        """
        params: dict[str, Any] = {
            "FILTER": {"FIND": query},
        }

        # user.get returns a list directly, not wrapped in a "users" key
        result = await self._request("user.get", params)

        # Result is a list of users directly
        if isinstance(result, list):
            users_data = result[:limit]
        else:
            users_data = []

        return [BitrixUser.model_validate(user) for user in users_data]
