"""Tests for MCP tools."""

import pytest
from httpx import Response

from bitrix_mcp import server
from bitrix_mcp.bitrix.client import Bitrix24Client
from bitrix_mcp.server import (
    _group_search,
    _task_comment_add,
    _task_create,
    _task_get,
    _task_list_by_user,
    _task_search,
    _user_search,
    get_client,
    set_client,
)


@pytest.fixture
def setup_client(mock_webhook_url, mock_bitrix_api):
    """Set up Bitrix24 client for tools."""
    client = Bitrix24Client(webhook_url=mock_webhook_url)
    set_client(client)
    yield client


class TestTaskSearch:
    """Tests for task_search tool."""

    @pytest.mark.asyncio
    async def test_task_search_basic(
        self, setup_client, sample_task_list_response, mock_bitrix_api
    ):
        """task_search should return formatted results with URL."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_response)
        )

        results = await _task_search(query="welcome email")

        assert len(results) == 2
        assert results[0]["id"] == 456
        assert results[0]["title"] == "Auto Send welcome email"
        assert results[0]["responsibleId"] == 7
        assert results[0]["groupId"] == 5
        assert results[0]["status"] == "pending"
        # URL should be generated from base_url
        assert (
            results[0]["url"] == "https://test.bitrix24.com/workgroups/group/5/tasks/task/view/456/"
        )

    @pytest.mark.asyncio
    async def test_task_search_with_limit(
        self, setup_client, sample_task_list_response, mock_bitrix_api
    ):
        """task_search should pass limit parameter."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_response)
        )

        await _task_search(query="test", limit=5)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["limit"] == 5

    @pytest.mark.asyncio
    async def test_task_search_no_results(self, setup_client, mock_bitrix_api):
        """task_search should handle empty results."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json={"result": {"tasks": []}})
        )

        results = await _task_search(query="nonexistent task xyz")

        assert results == []

    @pytest.mark.asyncio
    async def test_task_search_status_mapping(self, setup_client, mock_bitrix_api):
        """task_search should map status codes to strings."""
        response = {
            "result": {
                "tasks": [
                    {
                        "id": "1",
                        "title": "Pending",
                        "responsibleId": "1",
                        "groupId": "1",
                        "status": "2",
                    },
                    {
                        "id": "2",
                        "title": "In Progress",
                        "responsibleId": "1",
                        "groupId": "1",
                        "status": "3",
                    },
                    {
                        "id": "3",
                        "title": "Completed",
                        "responsibleId": "1",
                        "groupId": "1",
                        "status": "5",
                    },
                ]
            }
        }
        mock_bitrix_api.post("tasks.task.list").mock(return_value=Response(200, json=response))

        results = await _task_search(query="test")

        assert results[0]["status"] == "pending"
        assert results[1]["status"] == "in_progress"
        assert results[2]["status"] == "completed"


class TestTaskGet:
    """Tests for task_get tool."""

    @pytest.mark.asyncio
    async def test_task_get_basic(self, setup_client, sample_task_get_response, mock_bitrix_api):
        """task_get should return full task details with URL."""
        mock_bitrix_api.post("tasks.task.get").mock(
            return_value=Response(200, json=sample_task_get_response)
        )

        result = await _task_get(id=456)

        assert result["id"] == 456
        assert result["title"] == "Auto Send welcome email"
        assert result["description"] == "Any new sign up user, send welcome email."
        assert result["responsibleId"] == 7
        assert result["groupId"] == 5
        assert result["status"] == "pending"
        assert result["priority"] == "medium"
        assert result["attachmentFileIds"] == [1065, 1077]
        # URL should be generated from base_url
        assert result["url"] == "https://test.bitrix24.com/workgroups/group/5/tasks/task/view/456/"

    @pytest.mark.asyncio
    async def test_task_get_with_description(
        self, setup_client, sample_task_get_response, mock_bitrix_api
    ):
        """task_get should include description for AI analysis."""
        mock_bitrix_api.post("tasks.task.get").mock(
            return_value=Response(200, json=sample_task_get_response)
        )

        result = await _task_get(id=456)

        # Description is the key field for AI to analyze
        assert "description" in result
        assert result["description"] is not None
        assert len(result["description"]) > 0

    @pytest.mark.asyncio
    async def test_task_get_includes_parent_info(self, setup_client, mock_bitrix_api):
        """task_get should include parent ID for subtask context."""
        response = {
            "result": {
                "task": {
                    "id": "457",
                    "title": "Subtask",
                    "description": "A subtask",
                    "responsibleId": "7",
                    "groupId": "5",
                    "createdBy": "1",
                    "status": "2",
                    "deadline": None,
                    "parentId": "456",
                    "priority": "1",
                }
            }
        }
        mock_bitrix_api.post("tasks.task.get").mock(return_value=Response(200, json=response))

        result = await _task_get(id=457)

        assert result["parentId"] == 456

    @pytest.mark.asyncio
    async def test_task_get_include_comments(
        self,
        setup_client,
        sample_task_get_response,
        sample_task_comment_list_response,
        mock_bitrix_api,
    ):
        """task_get should include comments when includeComments=True."""
        mock_bitrix_api.post("tasks.task.get").mock(
            return_value=Response(200, json=sample_task_get_response)
        )
        mock_bitrix_api.post("task.commentitem.getlist").mock(
            return_value=Response(200, json=sample_task_comment_list_response)
        )

        result = await _task_get(id=456, includeComments=True)

        assert "comments" in result
        assert len(result["comments"]) == 2
        assert result["comments"][0]["id"] == 3155
        assert result["comments"][0]["authorId"] == 503
        assert result["comments"][0]["message"] == "Prepared new photos"
        assert result["comments"][1]["attachments"][0]["attachmentId"] == 973

        # Verify ORDER was sent (chronological sorting)
        import json

        comment_call = mock_bitrix_api.calls[1].request
        body = json.loads(comment_call.content)
        assert body["TASKID"] == 456
        assert body["ORDER"]["POST_DATE"] == "asc"


class TestTaskCommentAdd:
    """Tests for task_comment_add tool."""

    @pytest.mark.asyncio
    async def test_task_comment_add_basic(
        self, setup_client, sample_task_comment_add_response, mock_bitrix_api
    ):
        """task_comment_add should return created commentId and send correct payload."""
        mock_bitrix_api.post("task.commentitem.add").mock(
            return_value=Response(200, json=sample_task_comment_add_response)
        )

        result = await _task_comment_add(id=456, message="Hello from tool tests")

        assert result["taskId"] == 456
        assert result["commentId"] == 3158
        assert result["created"] is True

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["TASKID"] == 456
        assert body["fields"]["POST_MESSAGE"] == "Hello from tool tests"

    @pytest.mark.asyncio
    async def test_task_comment_add_api_error(
        self, setup_client, api_error_response, mock_bitrix_api
    ):
        """task_comment_add should re-raise API errors as RuntimeError."""
        mock_bitrix_api.post("task.commentitem.add").mock(
            return_value=Response(200, json=api_error_response)
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error"):
            await _task_comment_add(id=456, message="This will fail")


class TestTaskCreate:
    """Tests for task_create tool."""

    @pytest.mark.asyncio
    async def test_task_create_minimal(
        self, setup_client, sample_task_add_response, mock_bitrix_api
    ):
        """task_create should work with minimal required fields."""
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )

        result = await _task_create(
            title="New task",
            responsibleId=7,
        )

        assert result["id"] == 457
        assert result["title"] == "New task"

    @pytest.mark.asyncio
    async def test_task_create_full(
        self, setup_client, sample_task_add_response, sample_task_data, mock_bitrix_api
    ):
        """task_create should send all provided fields."""
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )

        result = await _task_create(
            title=sample_task_data["title"],
            responsibleId=sample_task_data["responsibleId"],
            description=sample_task_data["description"],
            groupId=sample_task_data["groupId"],
            parentId=sample_task_data["parentId"],
            priority=sample_task_data["priority"],
        )

        assert result["id"] == 457
        assert result["title"] == sample_task_data["title"]

        # Verify API was called with correct fields
        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        fields = body["fields"]

        assert fields["TITLE"] == sample_task_data["title"]
        assert fields["DESCRIPTION"] == sample_task_data["description"]
        assert fields["GROUP_ID"] == sample_task_data["groupId"]
        assert fields["PARENT_ID"] == sample_task_data["parentId"]

    @pytest.mark.asyncio
    async def test_task_create_subtask(
        self, setup_client, sample_task_add_response, mock_bitrix_api
    ):
        """task_create with parentId should create a subtask."""
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )

        await _task_create(
            title="Subtask",
            responsibleId=7,
            groupId=5,
            parentId=456,  # Parent task ID
        )

        # Verify PARENT_ID was sent
        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["fields"]["PARENT_ID"] == 456

    @pytest.mark.asyncio
    async def test_task_create_inherits_from_parent(
        self, setup_client, sample_task_add_response, mock_bitrix_api
    ):
        """task_create should copy responsibleId and groupId from parent."""
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )

        # Simulating the workflow: copy from parent task
        parent_responsible_id = 7  # From parent task
        parent_group_id = 5  # From parent task
        parent_id = 456

        await _task_create(
            title="Subtask",
            responsibleId=parent_responsible_id,  # Copied from parent
            groupId=parent_group_id,  # Copied from parent
            parentId=parent_id,
            description="Subtask description",
        )

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        fields = body["fields"]

        # Verify subtask inherits parent's properties
        assert fields["RESPONSIBLE_ID"] == parent_responsible_id
        assert fields["GROUP_ID"] == parent_group_id
        assert fields["PARENT_ID"] == parent_id


class TestToolClientManagement:
    """Tests for tool client management."""

    def test_get_client_without_env_var_raises(self, monkeypatch):
        """get_client should raise if it cannot be initialized (missing env var)."""
        server._client = None  # Reset client
        monkeypatch.delenv("BITRIX_WEBHOOK_URL", raising=False)
        with pytest.raises(RuntimeError, match="Bitrix24 client not initialized"):
            get_client()

    def test_set_client_stores_client(self, mock_webhook_url):
        """set_client should store the client instance."""
        client = Bitrix24Client(webhook_url=mock_webhook_url)
        set_client(client)
        assert get_client() is client


class TestUserSearch:
    """Tests for user_search tool."""

    @pytest.mark.asyncio
    async def test_user_search_basic(self, setup_client, sample_user_get_response, mock_bitrix_api):
        """user_search should return formatted results."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        results = await _user_search(query="John")

        # Should match both "John Doe" and "Johnny Smith"
        assert len(results) == 2
        assert results[0]["id"] == 7
        assert results[0]["name"] == "John Doe"
        assert results[0]["email"] == "john@company.com"

    @pytest.mark.asyncio
    async def test_user_search_no_results(self, setup_client, mock_bitrix_api):
        """user_search should handle empty results."""
        mock_bitrix_api.post("user.get").mock(return_value=Response(200, json={"result": []}))

        results = await _user_search(query="nonexistent user xyz")

        assert results == []

    @pytest.mark.asyncio
    async def test_user_search_name_formatting(
        self, setup_client, sample_single_user_response, mock_bitrix_api
    ):
        """user_search should format full name correctly."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_single_user_response)
        )

        results = await _user_search(query="John")

        # Name should be "FirstName LastName"
        assert results[0]["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_user_search_filters_by_last_name(
        self, setup_client, sample_user_get_response, mock_bitrix_api
    ):
        """user_search should filter by last name as well."""
        mock_bitrix_api.post("user.get").mock(
            return_value=Response(200, json=sample_user_get_response)
        )

        results = await _user_search(query="Doe")

        # Should only match "John Doe"
        assert len(results) == 1
        assert results[0]["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_user_search_pagination(
        self, setup_client, sample_user_list_page1, sample_user_list_page2, mock_bitrix_api
    ):
        """user_search should fetch all users via pagination and filter."""
        mock_bitrix_api.post("user.get").mock(
            side_effect=[
                Response(200, json=sample_user_list_page1),
                Response(200, json=sample_user_list_page2),
            ]
        )

        results = await _user_search(query="Phu")

        # Should find "Phu Nguyen" from page 2
        assert len(results) == 1
        assert results[0]["name"] == "Phu Nguyen"
        assert results[0]["id"] == 100


class TestTaskListByUser:
    """Tests for task_list_by_user tool."""

    @pytest.mark.asyncio
    async def test_task_list_by_user_basic(
        self, setup_client, sample_task_list_response, mock_bitrix_api
    ):
        """task_list_by_user should return tasks for a specific user with URL."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_response)
        )

        results = await _task_list_by_user(responsibleId=7)

        assert len(results) == 2
        assert results[0]["id"] == 456
        assert results[0]["responsibleId"] == 7
        # URL should be generated from base_url
        assert (
            results[0]["url"] == "https://test.bitrix24.com/workgroups/group/5/tasks/task/view/456/"
        )

    @pytest.mark.asyncio
    async def test_task_list_by_user_with_status(
        self, setup_client, sample_task_list_response, mock_bitrix_api
    ):
        """task_list_by_user should filter by status."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_response)
        )

        await _task_list_by_user(responsibleId=7, status="in_progress")

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["filter"]["RESPONSIBLE_ID"] == 7
        assert body["filter"]["STATUS"] == 3  # in_progress = 3

    @pytest.mark.asyncio
    async def test_task_list_by_user_no_results(self, setup_client, mock_bitrix_api):
        """task_list_by_user should handle empty results."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json={"result": {"tasks": []}})
        )

        results = await _task_list_by_user(responsibleId=999)

        assert results == []

    @pytest.mark.asyncio
    async def test_task_list_by_user_filter_params(
        self, setup_client, sample_task_list_response, mock_bitrix_api
    ):
        """task_list_by_user should send correct filter parameters."""
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_response)
        )

        await _task_list_by_user(responsibleId=7, status="pending", limit=25)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["filter"]["RESPONSIBLE_ID"] == 7
        assert body["filter"]["STATUS"] == 2  # pending = 2
        assert body["limit"] == 25


class TestGroupSearch:
    """Tests for group_search tool."""

    @pytest.mark.asyncio
    async def test_group_search_basic(
        self, setup_client, sample_group_search_response, mock_bitrix_api
    ):
        """group_search should return formatted group matches."""
        mock_bitrix_api.post("sonet_group.get").mock(
            return_value=Response(200, json=sample_group_search_response)
        )

        results = await _group_search(query="MusicFlowx", limit=10)

        assert len(results) == 2
        assert results[0]["id"] == 205
        assert results[0]["name"] == "MusicFlowx Development"
        assert results[1]["id"] == 206
        assert results[1]["name"] == "MusicFlowx QA"

    @pytest.mark.asyncio
    async def test_group_search_filter_params(
        self, setup_client, sample_group_search_response, mock_bitrix_api
    ):
        """group_search should send correct filter parameters."""
        mock_bitrix_api.post("sonet_group.get").mock(
            return_value=Response(200, json=sample_group_search_response)
        )

        await _group_search(query="MusicFlowx", limit=10)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["FILTER"]["%NAME"] == "MusicFlowx"
        assert body["ORDER"]["NAME"] == "ASC"
