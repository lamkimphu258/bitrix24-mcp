"""Bitrix24 API client with rate limiting and error handling."""

import asyncio
import logging
import os
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .types import (
    BitrixAPIError,
    BitrixConnectionError,
    BitrixGroup,
    BitrixTask,
    BitrixTaskComment,
    BitrixUser,
)

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

        # Extract base URL for generating task links
        self._base_url = self._extract_base_url()

    def _extract_base_url(self) -> str:
        """Extract base URL from webhook URL for generating task links.

        Example: https://example.bitrix24.com/rest/1/token/ -> https://example.bitrix24.com

        Returns:
            Base URL without the /rest/... path
        """
        parsed = urlparse(self.webhook_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def get_base_url(self) -> str:
        """Get the base URL for generating Bitrix24 links.

        Returns:
            Base URL (e.g., https://example.bitrix24.com)
        """
        return self._base_url

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

    async def task_commentitem_getlist(
        self,
        task_id: int,
        order: dict[str, str] | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[BitrixTaskComment]:
        """Get a list of comments for a task.

        Note:
            Bitrix24 marks task.commentitem.getlist as legacy for the "new task card"
            UI. Some portals may require using chat APIs instead. We still use this
            method because it is the dedicated REST endpoint for task comments.

        Args:
            task_id: Task ID
            order: Optional sorting object (e.g., {"POST_DATE": "asc"})
            filter: Optional filter object

        Returns:
            List of BitrixTaskComment objects
        """
        # Parameter order matters for this method in Bitrix24.
        params: dict[str, Any] = {"TASKID": task_id}
        if order is not None:
            params["ORDER"] = order
        if filter is not None:
            params["FILTER"] = filter

        result = await self._request("task.commentitem.getlist", params)

        if not isinstance(result, list):
            raise BitrixAPIError(
                "Unexpected response format from task.commentitem.getlist",
                error_code="UNEXPECTED_RESPONSE",
            )

        return [BitrixTaskComment.model_validate(item) for item in result]

    async def _user_list_all(self) -> list[dict[str, Any]]:
        """Fetch all users with automatic pagination.

        Bitrix24 API returns max 50 users per request.
        This method paginates through all results.

        Returns:
            List of raw user dictionaries from the API
        """
        all_users: list[dict[str, Any]] = []
        start = 0
        batch_size = 50

        while True:
            result = await self._request("user.get", {"start": start})

            if isinstance(result, list):
                all_users.extend(result)
                # If we got less than batch_size, we've reached the last page
                if len(result) < batch_size:
                    break
                start += batch_size
            else:
                # Unexpected response format, stop pagination
                break

        logger.debug(f"Fetched {len(all_users)} total users")
        return all_users

    async def user_get(self, query: str) -> list[BitrixUser]:
        """Search for users by name.

        Fetches all users with pagination and filters client-side by name.
        The Bitrix24 FIND filter is unreliable, so we filter locally.

        Args:
            query: Search query (matches against first name or last name)

        Returns:
            List of matching BitrixUser objects
        """
        all_users = await self._user_list_all()

        # Filter by name client-side (case-insensitive)
        query_lower = query.lower()
        matching_users = [
            user
            for user in all_users
            if query_lower in (user.get("NAME") or "").lower()
            or query_lower in (user.get("LAST_NAME") or "").lower()
        ]

        logger.debug(f"Found {len(matching_users)} users matching '{query}'")
        return [BitrixUser.model_validate(user) for user in matching_users]

    async def group_search(self, query: str, limit: int = 10) -> list[BitrixGroup]:
        """Search workgroups/scrums by name.

        Args:
            query: Group name query (substring match)
            limit: Maximum number of results to return

        Returns:
            List of BitrixGroup objects
        """
        params = {
            "FILTER": {"%NAME": query},
            "ORDER": {"NAME": "ASC"},
        }

        result = await self._request("sonet_group.get", params)

        groups_data: list[dict[str, Any]] = []
        if isinstance(result, list):
            groups_data = [g for g in result if isinstance(g, dict)]
        elif isinstance(result, dict):
            nested = result.get("result")
            if isinstance(nested, list):
                groups_data = [g for g in nested if isinstance(g, dict)]

        groups = [BitrixGroup.model_validate(group) for group in groups_data]
        return groups[: max(limit, 0)]
