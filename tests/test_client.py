"""Tests for Bitrix24 API client."""

import pytest
import respx
from httpx import Response

from bitrix_mcp.bitrix.client import Bitrix24Client, RateLimiter
from bitrix_mcp.bitrix.types import BitrixAPIError, BitrixConnectionError


class TestBitrix24ClientInitialization:
    """Tests for client initialization."""

    def test_client_with_valid_url(self, mock_webhook_url):
        """Client should initialize with valid webhook URL."""
        client = Bitrix24Client(webhook_url=mock_webhook_url)
        assert client.webhook_url == mock_webhook_url

    def test_client_adds_trailing_slash(self):
        """Client should add trailing slash to URL."""
        url = "https://test.bitrix24.com/rest/1/token"
        client = Bitrix24Client(webhook_url=url)
        assert client.webhook_url.endswith("/")

    def test_client_without_url_raises_error(self, monkeypatch):
        """Client should raise error if no URL provided."""
        monkeypatch.delenv("BITRIX_WEBHOOK_URL", raising=False)
        with pytest.raises(ValueError, match="webhook URL is required"):
            Bitrix24Client()

    def test_client_with_invalid_url_format(self):
        """Client should raise error for invalid URL format."""
        with pytest.raises(ValueError, match="Invalid webhook URL format"):
            Bitrix24Client(webhook_url="invalid-url")

    def test_client_from_env_var(self, monkeypatch, mock_webhook_url):
        """Client should use BITRIX_WEBHOOK_URL env var."""
        monkeypatch.setenv("BITRIX_WEBHOOK_URL", mock_webhook_url)
        client = Bitrix24Client()
        assert client.webhook_url == mock_webhook_url


class TestRateLimiter:
    """Tests for rate limiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_initial_requests(self):
        """Rate limiter should allow initial burst of requests."""
        limiter = RateLimiter(rate=2.0)
        # Should complete without waiting
        await limiter.acquire()
        await limiter.acquire()

    @pytest.mark.asyncio
    async def test_rate_limiter_has_correct_rate(self):
        """Rate limiter should have correct rate configuration."""
        limiter = RateLimiter(rate=5.0)
        assert limiter.rate == 5.0


class TestTaskList:
    """Tests for task_list method."""

    @pytest.mark.asyncio
    async def test_task_list_success(
        self, mock_webhook_url, sample_task_list_response, mock_bitrix_api
    ):
        """task_list should return list of tasks."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            tasks = await client.task_list(filter={"%TITLE": "welcome"})

        assert len(tasks) == 2
        assert tasks[0].id == "456"
        assert tasks[0].title == "Auto Send welcome email"
        assert tasks[0].responsible_id == "7"

    @pytest.mark.asyncio
    async def test_task_list_empty(self, mock_webhook_url, mock_bitrix_api):
        """task_list should handle empty results."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json={"result": {"tasks": []}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            tasks = await client.task_list(filter={"%TITLE": "nonexistent"})

        assert tasks == []

    @pytest.mark.asyncio
    async def test_task_list_with_limit(
        self, mock_webhook_url, sample_task_list_response, mock_bitrix_api
    ):
        """task_list should respect limit parameter."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.task_list(filter={}, limit=5)

        # Verify the request was made with correct limit
        request = mock_bitrix_api.calls[0].request
        import json
        body = json.loads(request.content)
        assert body["limit"] == 5


class TestTaskGet:
    """Tests for task_get method."""

    @pytest.mark.asyncio
    async def test_task_get_success(
        self, mock_webhook_url, sample_task_get_response, mock_bitrix_api
    ):
        """task_get should return task details."""
        mock_bitrix_api.post("tasks.task.get").mock(
            return_value=Response(200, json=sample_task_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            task = await client.task_get(task_id=456)

        assert task.id == "456"
        assert task.title == "Auto Send welcome email"
        assert task.description == "Any new sign up user, send welcome email."
        assert task.responsible_id == "7"

    @pytest.mark.asyncio
    async def test_task_get_not_found(
        self, mock_webhook_url, api_error_response, mock_bitrix_api
    ):
        """task_get should raise error for non-existent task."""
        mock_bitrix_api.post("tasks.task.get").mock(
            return_value=Response(200, json=api_error_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Task not found"):
                await client.task_get(task_id=99999)


class TestTaskAdd:
    """Tests for task_add method."""

    @pytest.mark.asyncio
    async def test_task_add_success(
        self, mock_webhook_url, sample_task_add_response, mock_bitrix_api
    ):
        """task_add should return created task ID."""
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            task_id = await client.task_add(
                title="Test task",
                responsible_id=7,
                description="Test description",
            )

        assert task_id == 457

    @pytest.mark.asyncio
    async def test_task_add_with_all_fields(
        self, mock_webhook_url, sample_task_add_response, sample_task_data, mock_bitrix_api
    ):
        """task_add should send all provided fields."""
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.task_add(
                title=sample_task_data["title"],
                responsible_id=sample_task_data["responsibleId"],
                description=sample_task_data["description"],
                group_id=sample_task_data["groupId"],
                parent_id=sample_task_data["parentId"],
                priority=sample_task_data["priority"],
            )

        # Verify the request contains all fields
        import json
        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        fields = body["fields"]

        assert fields["TITLE"] == sample_task_data["title"]
        assert fields["RESPONSIBLE_ID"] == sample_task_data["responsibleId"]
        assert fields["DESCRIPTION"] == sample_task_data["description"]
        assert fields["GROUP_ID"] == sample_task_data["groupId"]
        assert fields["PARENT_ID"] == sample_task_data["parentId"]
        assert fields["PRIORITY"] == sample_task_data["priority"]


class TestUserGet:
    """Tests for user_get method."""

    @pytest.mark.asyncio
    async def test_user_get_success(
        self, mock_webhook_url, sample_user_get_response, mock_bitrix_api
    ):
        """user_get should return list of users."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="John")

        assert len(users) == 2
        assert users[0].id == "7"
        assert users[0].name == "John"
        assert users[0].last_name == "Doe"
        assert users[0].email == "john@company.com"

    @pytest.mark.asyncio
    async def test_user_get_empty(self, mock_webhook_url, mock_bitrix_api):
        """user_get should handle empty results."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json={"result": []})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="nonexistent")

        assert users == []

    @pytest.mark.asyncio
    async def test_user_get_with_limit(
        self, mock_webhook_url, sample_user_get_response, mock_bitrix_api
    ):
        """user_get should respect limit parameter."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="John", limit=1)

        # Should return only 1 user due to limit
        assert len(users) == 1
        assert users[0].id == "7"


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_api_error_response(
        self, mock_webhook_url, api_error_response, mock_bitrix_api
    ):
        """Client should raise BitrixAPIError for API errors."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=api_error_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError):
                await client.task_list()

    @pytest.mark.asyncio
    async def test_http_error_response(self, mock_webhook_url, mock_bitrix_api):
        """Client should raise BitrixAPIError for HTTP errors."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError):
                await client.task_list()

