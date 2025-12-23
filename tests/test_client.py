"""Tests for Bitrix24 API client."""

import pytest
from httpx import Response

from bitrix_mcp.bitrix.client import Bitrix24Client, RateLimiter
from bitrix_mcp.bitrix.types import BitrixAPIError


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

    def test_client_extracts_base_url(self, mock_webhook_url):
        """Client should extract base URL from webhook URL."""
        client = Bitrix24Client(webhook_url=mock_webhook_url)
        # mock_webhook_url = "https://test.bitrix24.com/rest/1/test-token/"
        assert client.get_base_url() == "https://test.bitrix24.com"

    def test_client_extracts_base_url_various_formats(self):
        """Client should extract base URL from various webhook URL formats."""
        # Standard format
        client1 = Bitrix24Client(webhook_url="https://example.bitrix24.com/rest/1/token/")
        assert client1.get_base_url() == "https://example.bitrix24.com"

        # Custom domain
        client2 = Bitrix24Client(webhook_url="https://intranet.usea.global/rest/1665/token/")
        assert client2.get_base_url() == "https://intranet.usea.global"


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
    async def test_task_get_not_found(self, mock_webhook_url, api_error_response, mock_bitrix_api):
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
        """user_get should return list of users matching query."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="John")

        # Should match both "John Doe" and "Johnny Smith" (NAME contains "john")
        assert len(users) == 2
        assert users[0].id == "7"
        assert users[0].name == "John"
        assert users[0].last_name == "Doe"
        assert users[0].email == "john@company.com"

    @pytest.mark.asyncio
    async def test_user_get_empty(self, mock_webhook_url, mock_bitrix_api):
        """user_get should handle empty results."""
        mock_bitrix_api.post("user.get").mock(return_value=Response(200, json={"result": []}))

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="nonexistent")

        assert users == []

    @pytest.mark.asyncio
    async def test_user_get_filters_by_name(
        self, mock_webhook_url, sample_user_get_response, mock_bitrix_api
    ):
        """user_get should filter users by first or last name."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            # Search by last name
            users = await client.user_get(query="Doe")

        # Should only match "John Doe" (LAST_NAME contains "doe")
        assert len(users) == 1
        assert users[0].last_name == "Doe"

    @pytest.mark.asyncio
    async def test_user_get_case_insensitive(
        self, mock_webhook_url, sample_user_get_response, mock_bitrix_api
    ):
        """user_get should filter case-insensitively."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="JOHN")

        # Should match both users (case-insensitive)
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_user_get_pagination(
        self, mock_webhook_url, sample_user_list_page1, sample_user_list_page2, mock_bitrix_api
    ):
        """user_get should paginate through all users."""
        # First call returns 50 users (full page), second call returns 26 users (last page)
        mock_bitrix_api.post("user.get").mock(
            side_effect=[
                Response(200, json=sample_user_list_page1),
                Response(200, json=sample_user_list_page2),
            ]
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="Phu")

        # Should have made 2 API calls
        assert len(mock_bitrix_api.calls) == 2

        # Verify pagination parameters
        import json

        first_call = json.loads(mock_bitrix_api.calls[0].request.content)
        second_call = json.loads(mock_bitrix_api.calls[1].request.content)
        assert first_call.get("start") == 0
        assert second_call.get("start") == 50

        # Should find "Phu" user from page 2
        assert len(users) == 1
        assert users[0].name == "Phu"
        assert users[0].last_name == "Nguyen"

    @pytest.mark.asyncio
    async def test_user_get_no_match(
        self, mock_webhook_url, sample_user_get_response, mock_bitrix_api
    ):
        """user_get should return empty list when no users match query."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            users = await client.user_get(query="xyz123nonexistent")

        assert users == []


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_api_error_response(self, mock_webhook_url, api_error_response, mock_bitrix_api):
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


class TestGroupGet:
    """Tests for group_get method."""

    @pytest.mark.asyncio
    async def test_group_get_success(
        self, mock_webhook_url, sample_group_get_response, mock_bitrix_api
    ):
        """group_get should return group details."""
        mock_bitrix_api.post("sonet_group.get").mock(
            return_value=Response(200, json=sample_group_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            group = await client.group_get(group_id=205)

        assert group.id == "205"
        assert group.name == "MusicFlowx Development"
        assert group.description == "Development tasks for MusicFlowx platform"
        assert group.owner_id == "22"
        assert group.project == "Y"
        assert group.scrum_master_id == "1665"

    @pytest.mark.asyncio
    async def test_group_get_not_found(self, mock_webhook_url, mock_bitrix_api):
        """group_get should raise error for non-existent group."""
        mock_bitrix_api.post("sonet_group.get").mock(
            return_value=Response(200, json={"result": []})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Group 999 not found"):
                await client.group_get(group_id=999)

    @pytest.mark.asyncio
    async def test_group_get_filter_params(
        self, mock_webhook_url, sample_group_get_response, mock_bitrix_api
    ):
        """group_get should send correct filter parameters."""
        mock_bitrix_api.post("sonet_group.get").mock(
            return_value=Response(200, json=sample_group_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.group_get(group_id=205)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["FILTER"]["ID"] == 205
