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
        assert "PARENT_ID" in body["select"]


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
        assert task.stage_id == "11"

    @pytest.mark.asyncio
    async def test_task_get_webdav_files_false_is_normalized(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """task_get should tolerate ufTaskWebdavFiles=false from Bitrix24."""
        response = {
            "result": {
                "task": {
                    "id": "456",
                    "title": "Auto Send welcome email",
                    "description": "Any new sign up user, send welcome email.",
                    "responsibleId": "7",
                    "groupId": "5",
                    "stageId": "11",
                    "createdBy": "1",
                    "status": "2",
                    "deadline": None,
                    "parentId": None,
                    "priority": "1",
                    "ufTaskWebdavFiles": False,
                }
            }
        }
        mock_bitrix_api.post("tasks.task.get").mock(return_value=Response(200, json=response))

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            task = await client.task_get(task_id=456)

        assert task.attachment_file_ids == []

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


class TestTaskUpdate:
    """Tests for task_update method."""

    @pytest.mark.asyncio
    async def test_task_update_success_sends_fields(self, mock_webhook_url, mock_bitrix_api):
        """task_update should send correct payload and return raw result."""
        mock_bitrix_api.post("tasks.task.update").mock(
            return_value=Response(200, json={"result": True})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            result = await client.task_update(
                task_id=456,
                title="Updated title",
                description="Updated description",
                priority=2,
                status=3,
                responsible_id=7,
                accomplices=[8, 9],
                auditors=[10],
                deadline="2025-12-31T23:59:00+02:00",
                start_date_plan="2025-12-01T10:00:00+02:00",
                end_date_plan="2025-12-02T18:00:00+02:00",
                group_id=5,
                parent_id=0,
                stage_id=11,
            )

        assert result is True

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)

        assert body["taskId"] == 456
        fields = body["fields"]
        assert fields["TITLE"] == "Updated title"
        assert fields["DESCRIPTION"] == "Updated description"
        assert fields["PRIORITY"] == 2
        assert fields["STATUS"] == 3
        assert fields["RESPONSIBLE_ID"] == 7
        assert fields["ACCOMPLICES"] == [8, 9]
        assert fields["AUDITORS"] == [10]
        assert fields["DEADLINE"] == "2025-12-31T23:59:00+02:00"
        assert fields["START_DATE_PLAN"] == "2025-12-01T10:00:00+02:00"
        assert fields["END_DATE_PLAN"] == "2025-12-02T18:00:00+02:00"
        assert fields["GROUP_ID"] == 5
        assert fields["PARENT_ID"] == 0
        assert fields["STAGE_ID"] == 11

    @pytest.mark.asyncio
    async def test_task_update_requires_at_least_one_field(self, mock_webhook_url):
        """task_update should raise ValueError when no fields are provided."""
        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(ValueError, match="At least one field must be provided"):
                await client.task_update(task_id=456)


class TestTaskCommentItemAdd:
    """Tests for task_commentitem_add method."""

    @pytest.mark.asyncio
    async def test_task_commentitem_add_success(
        self, mock_webhook_url, sample_task_comment_add_response, mock_bitrix_api
    ):
        """task_commentitem_add should return created comment ID."""
        mock_bitrix_api.post("task.commentitem.add").mock(
            return_value=Response(200, json=sample_task_comment_add_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            comment_id = await client.task_commentitem_add(task_id=456, message="Hello from tests")

        assert comment_id == 3158

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["TASKID"] == 456
        assert body["fields"]["POST_MESSAGE"] == "Hello from tests"

    @pytest.mark.asyncio
    async def test_task_commentitem_add_accepts_wrapped_response(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """task_commentitem_add should handle portals that wrap the comment id in an object."""
        mock_bitrix_api.post("task.commentitem.add").mock(
            return_value=Response(200, json={"result": {"ID": "4001"}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            comment_id = await client.task_commentitem_add(task_id=456, message="Wrapped")

        assert comment_id == 4001


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


class TestGroupSearch:
    """Tests for group_search method."""

    @pytest.mark.asyncio
    async def test_group_search_success(
        self, mock_webhook_url, sample_group_search_response, mock_bitrix_api
    ):
        """group_search should return matching groups (limited)."""
        mock_bitrix_api.post("sonet_group.get").mock(
            return_value=Response(200, json=sample_group_search_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            groups = await client.group_search(query="MusicFlowx", limit=1)

        assert len(groups) == 1
        assert groups[0].id == "205"
        assert groups[0].name == "MusicFlowx Development"

    @pytest.mark.asyncio
    async def test_group_search_filter_params(
        self, mock_webhook_url, sample_group_search_response, mock_bitrix_api
    ):
        """group_search should send correct filter parameters."""
        mock_bitrix_api.post("sonet_group.get").mock(
            return_value=Response(200, json=sample_group_search_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.group_search(query="MusicFlowx", limit=10)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["FILTER"]["%NAME"] == "MusicFlowx"
        assert body["ORDER"]["NAME"] == "ASC"


class TestScrumEpicList:
    """Tests for scrum_epic_list method."""

    @pytest.mark.asyncio
    async def test_scrum_epic_list_success(
        self, mock_webhook_url, sample_scrum_epic_list_response, mock_bitrix_api
    ):
        """scrum_epic_list should return list of epics."""
        mock_bitrix_api.post("tasks.api.scrum.epic.list").mock(
            return_value=Response(200, json=sample_scrum_epic_list_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            epics = await client.scrum_epic_list(
                filter={"GROUP_ID": 5},
                order={"ID": "asc"},
                start=0,
            )

        assert len(epics) == 2
        assert epics[0].id == 1
        assert epics[0].group_id == 5
        assert epics[0].name == "Dashboard"

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["filter"]["GROUP_ID"] == 5
        assert body["order"]["ID"] == "asc"
        assert body["start"] == 0


class TestScrumTaskGet:
    """Tests for scrum_task_get method."""

    @pytest.mark.asyncio
    async def test_scrum_task_get_success(
        self, mock_webhook_url, sample_scrum_task_get_response, mock_bitrix_api
    ):
        """scrum_task_get should return scrum task fields."""
        mock_bitrix_api.post("tasks.api.scrum.task.get").mock(
            return_value=Response(200, json=sample_scrum_task_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            scrum_task = await client.scrum_task_get(task_id=456)

        assert scrum_task.entity_id == 2
        assert scrum_task.story_points == "2"
        assert scrum_task.epic_id == 1

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 456


class TestScrumTaskUpdate:
    """Tests for scrum_task_update method."""

    @pytest.mark.asyncio
    async def test_scrum_task_update_success(
        self, mock_webhook_url, sample_scrum_task_update_response, mock_bitrix_api
    ):
        """scrum_task_update should send correct payload and return raw result."""
        mock_bitrix_api.post("tasks.api.scrum.task.update").mock(
            return_value=Response(200, json=sample_scrum_task_update_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            result = await client.scrum_task_update(
                task_id=456,
                entity_id=2,
                story_points="8",
                epic_id=1,
                sort=10,
            )

        assert result["status"] == "success"
        assert result["data"] is True
        assert result["errors"] == []

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 456
        assert body["fields"]["entityId"] == 2
        assert body["fields"]["storyPoints"] == "8"
        assert body["fields"]["epicId"] == 1
        assert body["fields"]["sort"] == 10

    @pytest.mark.asyncio
    async def test_scrum_task_update_accepts_boolean_result(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """scrum_task_update should normalize boolean results into a dict response."""
        mock_bitrix_api.post("tasks.api.scrum.task.update").mock(
            return_value=Response(200, json={"result": True})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            result = await client.scrum_task_update(task_id=456, epic_id=1)

        assert result == {"status": "success", "data": True, "errors": []}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 456
        assert body["fields"]["epicId"] == 1
