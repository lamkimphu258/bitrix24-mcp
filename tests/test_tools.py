"""Tests for MCP tools."""

import pytest
from httpx import Response

from bitrix_mcp import server
from bitrix_mcp.bitrix.client import Bitrix24Client
from bitrix_mcp.bitrix.types import BitrixConnectionError
from bitrix_mcp.server import (
    _crm_deal_add,
    _crm_deal_delete,
    _crm_deal_fields,
    _crm_deal_get,
    _crm_deal_list,
    _crm_deal_productrows_get,
    _crm_deal_update,
    _crm_lead_add,
    _crm_lead_delete,
    _crm_lead_get,
    _crm_lead_list,
    _crm_lead_productrows_get,
    _crm_lead_update,
    _group_search,
    _scrum_backlog_tasks,
    _scrum_epic_list,
    _scrum_task_create,
    _scrum_task_get,
    _scrum_task_update,
    _task_comment_add,
    _task_create,
    _task_get,
    _task_list_by_user,
    _task_search,
    _task_stages_get,
    _task_stages_move_task,
    _task_update,
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
        assert results[0]["parentId"] is None
        assert results[0]["status"] == "pending"
        # URL should be generated from base_url
        assert (
            results[0]["url"] == "https://test.bitrix24.com/workgroups/group/5/tasks/task/view/456/"
        )

    @pytest.mark.asyncio
    async def test_task_search_includes_parent_id(self, setup_client, mock_bitrix_api):
        """task_search should include parentId when task is a subtask."""
        response = {
            "result": {
                "tasks": [
                    {
                        "id": "457",
                        "title": "Subtask",
                        "responsibleId": "7",
                        "groupId": "5",
                        "status": "2",
                        "parentId": "456",
                    }
                ]
            }
        }
        mock_bitrix_api.post("tasks.task.list").mock(return_value=Response(200, json=response))

        results = await _task_search(query="Subtask")

        assert len(results) == 1
        assert results[0]["id"] == 457
        assert results[0]["parentId"] == 456

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
        assert result["stageId"] == 11
        assert result["status"] == "pending"
        assert result["priority"] == "medium"
        assert result["attachmentFileIds"] == [1065, 1077]
        # URL should be generated from base_url
        assert result["url"] == "https://test.bitrix24.com/workgroups/group/5/tasks/task/view/456/"

        # Verify STAGE_ID was requested in select
        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert "STAGE_ID" in body["select"]

    @pytest.mark.asyncio
    async def test_task_get_webdav_files_false_returns_empty_list(
        self, setup_client, mock_bitrix_api
    ):
        """task_get should treat ufTaskWebdavFiles=false as an empty attachment list."""
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

        result = await _task_get(id=456)

        assert result["attachmentFileIds"] == []
        assert result["stageId"] == 11

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


class TestCrmLeadGet:
    """Tests for crm_lead_get tool."""

    @pytest.mark.asyncio
    async def test_crm_lead_get_basic(
        self, setup_client, sample_crm_lead_get_response, mock_bitrix_api
    ):
        """crm_lead_get should return normalized lead details."""
        mock_bitrix_api.post("crm.lead.get").mock(
            return_value=Response(200, json=sample_crm_lead_get_response)
        )

        result = await _crm_lead_get(id=610)

        assert result["id"] == 610
        assert result["title"] == "Lead from Website"
        assert result["statusId"] == "NEW"
        assert result["opened"] is True
        assert result["assignedById"] == 1
        assert result["companyId"] == 9
        assert result["contactId"] == 84
        assert result["userFields"]["UF_CRM_1721244482250"] == "Custom value"
        assert result["extraFields"]["IS_RETURN_CUSTOMER"] == "N"

    @pytest.mark.asyncio
    async def test_crm_lead_get_api_error(self, setup_client, mock_bitrix_api):
        """crm_lead_get should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.lead.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Lead not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_lead_get(id=99999)

    @pytest.mark.asyncio
    async def test_crm_lead_get_connection_error(self, setup_client, monkeypatch):
        """crm_lead_get should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_lead_get", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_lead_get(id=610)


class TestCrmLeadList:
    """Tests for crm_lead_list tool."""

    @pytest.mark.asyncio
    async def test_crm_lead_list_basic(
        self, setup_client, sample_crm_lead_list_response, mock_bitrix_api
    ):
        """crm_lead_list should return lead rows with pagination metadata."""
        mock_bitrix_api.post("crm.lead.list").mock(
            return_value=Response(200, json=sample_crm_lead_list_response)
        )

        result = await _crm_lead_list(
            filter={"STATUS_ID": "NEW"},
            order={"TITLE": "ASC"},
            select=["ID", "TITLE", "STATUS_ID"],
            start=0,
        )

        assert len(result["items"]) == 2
        assert result["items"][0]["ID"] == "610"
        assert result["total"] == 95
        assert result["next"] == 50
        assert result["hasMore"] is True
        assert result["start"] == 0

    @pytest.mark.asyncio
    async def test_crm_lead_list_has_more_false_when_next_missing(
        self, setup_client, mock_bitrix_api
    ):
        """crm_lead_list should set hasMore=False when next is absent."""
        mock_bitrix_api.post("crm.lead.list").mock(
            return_value=Response(
                200,
                json={"result": [{"ID": "610", "TITLE": "Lead from Website"}], "total": 1},
            )
        )

        result = await _crm_lead_list(start=50)

        assert len(result["items"]) == 1
        assert result["total"] == 1
        assert result["next"] is None
        assert result["hasMore"] is False
        assert result["start"] == 50

    @pytest.mark.asyncio
    async def test_crm_lead_list_api_error(self, setup_client, mock_bitrix_api):
        """crm_lead_list should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.lead.list").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Access denied"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_lead_list()

    @pytest.mark.asyncio
    async def test_crm_lead_list_connection_error(self, setup_client, monkeypatch):
        """crm_lead_list should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_lead_list", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_lead_list()


class TestCrmLeadProductRowsGet:
    """Tests for crm_lead_productrows_get tool."""

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_basic(
        self, setup_client, sample_crm_lead_productrows_get_response, mock_bitrix_api
    ):
        """crm_lead_productrows_get should return id/rows."""
        mock_bitrix_api.post("crm.lead.productrows.get").mock(
            return_value=Response(200, json=sample_crm_lead_productrows_get_response)
        )

        result = await _crm_lead_productrows_get(id=610)

        assert result["id"] == 610
        assert len(result["rows"]) == 2
        assert result["rows"][0]["PRODUCT_ID"] == "101"
        assert result["rows"][1]["PRODUCT_ID"] == "102"

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 610

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_api_error(self, setup_client, mock_bitrix_api):
        """crm_lead_productrows_get should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.lead.productrows.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Lead not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_lead_productrows_get(id=99999)

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_connection_error(self, setup_client, monkeypatch):
        """crm_lead_productrows_get should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_lead_productrows_get", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_lead_productrows_get(id=610)


class TestCrmLeadAdd:
    """Tests for crm_lead_add tool."""

    @pytest.mark.asyncio
    async def test_crm_lead_add_basic(
        self, setup_client, sample_crm_lead_add_response, mock_bitrix_api
    ):
        """crm_lead_add should return id and created flag."""
        mock_bitrix_api.post("crm.lead.add").mock(
            return_value=Response(200, json=sample_crm_lead_add_response)
        )

        fields = {
            "TITLE": "Lead from Website",
            "STATUS_ID": "NEW",
            "OPPORTUNITY": "1200.00",
            "CURRENCY_ID": "USD",
        }
        params = {"REGISTER_SONET_EVENT": "Y"}
        result = await _crm_lead_add(fields=fields, params=params)

        assert result == {"id": 612, "created": True}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["fields"] == fields
        assert body["params"] == params

    @pytest.mark.asyncio
    async def test_crm_lead_add_rejects_empty_fields(self, setup_client):
        """crm_lead_add should reject empty fields."""
        with pytest.raises(RuntimeError, match="must not be empty"):
            await _crm_lead_add(fields={})

    @pytest.mark.asyncio
    async def test_crm_lead_add_api_error(self, setup_client, mock_bitrix_api):
        """crm_lead_add should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.lead.add").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Access denied"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_lead_add(fields={"TITLE": "Blocked Lead"})

    @pytest.mark.asyncio
    async def test_crm_lead_add_connection_error(self, setup_client, monkeypatch):
        """crm_lead_add should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_lead_add", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_lead_add(fields={"TITLE": "New Lead"})


class TestCrmLeadUpdate:
    """Tests for crm_lead_update tool."""

    @pytest.mark.asyncio
    async def test_crm_lead_update_basic(
        self, setup_client, sample_crm_lead_update_response, mock_bitrix_api
    ):
        """crm_lead_update should return id and updated flag."""
        mock_bitrix_api.post("crm.lead.update").mock(
            return_value=Response(200, json=sample_crm_lead_update_response)
        )

        fields = {"TITLE": "Updated Lead Title", "STATUS_ID": "IN_PROCESS"}
        params = {"REGISTER_SONET_EVENT": "N"}
        result = await _crm_lead_update(id=610, fields=fields, params=params)

        assert result == {"id": 610, "updated": True}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 610
        assert body["fields"] == fields
        assert body["params"] == params

    @pytest.mark.asyncio
    async def test_crm_lead_update_rejects_empty_fields(self, setup_client):
        """crm_lead_update should reject empty fields."""
        with pytest.raises(RuntimeError, match="must not be empty"):
            await _crm_lead_update(id=610, fields={})

    @pytest.mark.asyncio
    async def test_crm_lead_update_api_error(self, setup_client, mock_bitrix_api):
        """crm_lead_update should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.lead.update").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Update denied"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_lead_update(id=610, fields={"TITLE": "Blocked"})

    @pytest.mark.asyncio
    async def test_crm_lead_update_connection_error(self, setup_client, monkeypatch):
        """crm_lead_update should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_lead_update", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_lead_update(id=610, fields={"TITLE": "Updated"})


class TestCrmLeadDelete:
    """Tests for crm_lead_delete tool."""

    @pytest.mark.asyncio
    async def test_crm_lead_delete_basic(
        self, setup_client, sample_crm_lead_delete_response, mock_bitrix_api
    ):
        """crm_lead_delete should return id and deleted flag."""
        mock_bitrix_api.post("crm.lead.delete").mock(
            return_value=Response(200, json=sample_crm_lead_delete_response)
        )

        result = await _crm_lead_delete(id=610)
        assert result == {"id": 610, "deleted": True}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 610

    @pytest.mark.asyncio
    async def test_crm_lead_delete_api_error(self, setup_client, mock_bitrix_api):
        """crm_lead_delete should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.lead.delete").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Lead not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_lead_delete(id=99999)

    @pytest.mark.asyncio
    async def test_crm_lead_delete_connection_error(self, setup_client, monkeypatch):
        """crm_lead_delete should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_lead_delete", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_lead_delete(id=610)


class TestCrmDealGet:
    """Tests for crm_deal_get tool."""

    @pytest.mark.asyncio
    async def test_crm_deal_get_basic(
        self, setup_client, sample_crm_deal_get_response, mock_bitrix_api
    ):
        """crm_deal_get should return normalized deal details."""
        mock_bitrix_api.post("crm.deal.get").mock(
            return_value=Response(200, json=sample_crm_deal_get_response)
        )

        result = await _crm_deal_get(id=410)

        assert result["id"] == 410
        assert result["title"] == "New Deal #1"
        assert result["categoryId"] == 0
        assert result["stageId"] == "PREPARATION"
        assert result["isManualOpportunity"] is True
        assert result["opened"] is True
        assert result["closed"] is False
        assert result["companyId"] == 9
        assert result["assignedById"] == 1
        assert result["lastActivityBy"] == 1
        assert result["userFields"]["UF_CRM_1721244482250"] == "Hello world!"
        assert result["parentIds"]["PARENT_ID_153"] == 22

    @pytest.mark.asyncio
    async def test_crm_deal_get_api_error(self, setup_client, mock_bitrix_api):
        """crm_deal_get should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.deal.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_deal_get(id=99999)

    @pytest.mark.asyncio
    async def test_crm_deal_get_connection_error(self, setup_client, monkeypatch):
        """crm_deal_get should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_deal_get", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_deal_get(id=410)


class TestCrmDealFields:
    """Tests for crm_deal_fields tool."""

    @pytest.mark.asyncio
    async def test_crm_deal_fields_basic(
        self, setup_client, sample_crm_deal_fields_response, mock_bitrix_api
    ):
        """crm_deal_fields should return a field-definition map."""
        mock_bitrix_api.post("crm.deal.fields").mock(
            return_value=Response(200, json=sample_crm_deal_fields_response)
        )

        result = await _crm_deal_fields()

        assert "ID" in result
        assert "TITLE" in result
        assert "CONTACT_ID" in result
        assert result["CONTACT_ID"]["type"] == "crm_contact"

    @pytest.mark.asyncio
    async def test_crm_deal_fields_api_error(self, setup_client, mock_bitrix_api):
        """crm_deal_fields should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.deal.fields").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_deal_fields()

    @pytest.mark.asyncio
    async def test_crm_deal_fields_connection_error(self, setup_client, monkeypatch):
        """crm_deal_fields should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_deal_fields", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_deal_fields()


class TestCrmDealList:
    """Tests for crm_deal_list tool."""

    @pytest.mark.asyncio
    async def test_crm_deal_list_basic(
        self, setup_client, sample_crm_deal_list_response, mock_bitrix_api
    ):
        """crm_deal_list should return deal rows with pagination metadata."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(200, json=sample_crm_deal_list_response)
        )

        result = await _crm_deal_list(
            filter={"CATEGORY_ID": 0},
            order={"TITLE": "ASC"},
            select=["ID", "TITLE", "STAGE_ID"],
            start=0,
        )

        assert len(result["items"]) == 2
        assert result["items"][0]["ID"] == "410"
        assert result["items"][0]["TITLE"] == "New Deal #1"
        assert result["total"] == 120
        assert result["next"] == 50
        assert result["hasMore"] is True
        assert result["start"] == 0

    @pytest.mark.asyncio
    async def test_crm_deal_list_contact_id_shortcut(
        self, setup_client, sample_crm_deal_list_response, mock_bitrix_api
    ):
        """crm_deal_list should map contactId to CONTACT_ID filter."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(200, json=sample_crm_deal_list_response)
        )

        await _crm_deal_list(contactId=84)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["filter"]["CONTACT_ID"] == 84

    @pytest.mark.asyncio
    async def test_crm_deal_list_contact_ids_not_supported(self, setup_client):
        """crm_deal_list should reject CONTACT_IDS because Bitrix does not support it."""
        with pytest.raises(RuntimeError, match="CONTACT_IDS"):
            await _crm_deal_list(filter={"CONTACT_IDS": [84, 85]})

    @pytest.mark.asyncio
    async def test_crm_deal_list_conflicting_contact_filters(self, setup_client):
        """crm_deal_list should reject conflicting CONTACT_ID and contactId values."""
        with pytest.raises(RuntimeError, match="Conflicting contact filters"):
            await _crm_deal_list(filter={"CONTACT_ID": 85}, contactId=84)

    @pytest.mark.asyncio
    async def test_crm_deal_list_has_more_false_when_next_missing(
        self, setup_client, mock_bitrix_api
    ):
        """crm_deal_list should set hasMore=False when next is absent."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(
                200,
                json={"result": [{"ID": "410", "TITLE": "New Deal #1"}], "total": 1},
            )
        )

        result = await _crm_deal_list(start=50)

        assert len(result["items"]) == 1
        assert result["total"] == 1
        assert result["next"] is None
        assert result["hasMore"] is False
        assert result["start"] == 50

    @pytest.mark.asyncio
    async def test_crm_deal_list_api_error(self, setup_client, mock_bitrix_api):
        """crm_deal_list should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_deal_list()

    @pytest.mark.asyncio
    async def test_crm_deal_list_connection_error(self, setup_client, monkeypatch):
        """crm_deal_list should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_deal_list", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_deal_list()


class TestCrmDealProductRowsGet:
    """Tests for crm_deal_productrows_get tool."""

    @pytest.mark.asyncio
    async def test_crm_deal_productrows_get_basic(
        self, setup_client, sample_crm_deal_productrows_get_response, mock_bitrix_api
    ):
        """crm_deal_productrows_get should return dealId/items/count."""
        mock_bitrix_api.post("crm.deal.productrows.get").mock(
            return_value=Response(200, json=sample_crm_deal_productrows_get_response)
        )

        result = await _crm_deal_productrows_get(id=410)

        assert result["dealId"] == 410
        assert result["count"] == 2
        assert result["items"][0]["PRODUCT_ID"] == "101"
        assert result["items"][1]["PRODUCT_ID"] == "102"

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 410

    @pytest.mark.asyncio
    async def test_crm_deal_productrows_get_api_error(self, setup_client, mock_bitrix_api):
        """crm_deal_productrows_get should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.deal.productrows.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Deal not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_deal_productrows_get(id=99999)

    @pytest.mark.asyncio
    async def test_crm_deal_productrows_get_connection_error(self, setup_client, monkeypatch):
        """crm_deal_productrows_get should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_deal_productrows_get", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_deal_productrows_get(id=410)


class TestCrmDealAdd:
    """Tests for crm_deal_add tool."""

    @pytest.mark.asyncio
    async def test_crm_deal_add_basic(
        self, setup_client, sample_crm_deal_add_response, mock_bitrix_api
    ):
        """crm_deal_add should return id and created flag."""
        mock_bitrix_api.post("crm.deal.add").mock(
            return_value=Response(200, json=sample_crm_deal_add_response)
        )

        fields = {
            "TITLE": "New Deal #2",
            "STAGE_ID": "NEW",
            "OPPORTUNITY": "1500.00",
            "CURRENCY_ID": "USD",
        }
        result = await _crm_deal_add(fields=fields)

        assert result == {"id": 512, "created": True}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["fields"] == fields

    @pytest.mark.asyncio
    async def test_crm_deal_add_rejects_empty_fields(self, setup_client):
        """crm_deal_add should reject empty fields."""
        with pytest.raises(RuntimeError, match="must not be empty"):
            await _crm_deal_add(fields={})

    @pytest.mark.asyncio
    async def test_crm_deal_add_api_error(self, setup_client, mock_bitrix_api):
        """crm_deal_add should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.deal.add").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Access denied"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_deal_add(fields={"TITLE": "Blocked Deal"})

    @pytest.mark.asyncio
    async def test_crm_deal_add_connection_error(self, setup_client, monkeypatch):
        """crm_deal_add should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_deal_add", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_deal_add(fields={"TITLE": "New Deal"})


class TestCrmDealUpdate:
    """Tests for crm_deal_update tool."""

    @pytest.mark.asyncio
    async def test_crm_deal_update_basic(
        self, setup_client, sample_crm_deal_update_response, mock_bitrix_api
    ):
        """crm_deal_update should return id and updated flag."""
        mock_bitrix_api.post("crm.deal.update").mock(
            return_value=Response(200, json=sample_crm_deal_update_response)
        )

        fields = {"TITLE": "Updated Deal Title", "STAGE_ID": "PREPAYMENT_INVOICE"}
        result = await _crm_deal_update(id=410, fields=fields)

        assert result == {"id": 410, "updated": True}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 410
        assert body["fields"] == fields

    @pytest.mark.asyncio
    async def test_crm_deal_update_rejects_invalid_id(self, setup_client):
        """crm_deal_update should reject non-positive IDs."""
        with pytest.raises(RuntimeError, match="greater than 0"):
            await _crm_deal_update(id=0, fields={"TITLE": "Invalid"})

    @pytest.mark.asyncio
    async def test_crm_deal_update_rejects_empty_fields(self, setup_client):
        """crm_deal_update should reject empty fields."""
        with pytest.raises(RuntimeError, match="must not be empty"):
            await _crm_deal_update(id=410, fields={})

    @pytest.mark.asyncio
    async def test_crm_deal_update_api_error(self, setup_client, mock_bitrix_api):
        """crm_deal_update should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.deal.update").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Update denied"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_deal_update(id=410, fields={"TITLE": "Blocked"})

    @pytest.mark.asyncio
    async def test_crm_deal_update_connection_error(self, setup_client, monkeypatch):
        """crm_deal_update should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_deal_update", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_deal_update(id=410, fields={"TITLE": "Updated"})


class TestCrmDealDelete:
    """Tests for crm_deal_delete tool."""

    @pytest.mark.asyncio
    async def test_crm_deal_delete_basic(
        self, setup_client, sample_crm_deal_delete_response, mock_bitrix_api
    ):
        """crm_deal_delete should return id and deleted flag."""
        mock_bitrix_api.post("crm.deal.delete").mock(
            return_value=Response(200, json=sample_crm_deal_delete_response)
        )

        result = await _crm_deal_delete(id=410)
        assert result == {"id": 410, "deleted": True}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 410

    @pytest.mark.asyncio
    async def test_crm_deal_delete_rejects_invalid_id(self, setup_client):
        """crm_deal_delete should reject non-positive IDs."""
        with pytest.raises(RuntimeError, match="greater than 0"):
            await _crm_deal_delete(id=0)

    @pytest.mark.asyncio
    async def test_crm_deal_delete_api_error(self, setup_client, mock_bitrix_api):
        """crm_deal_delete should map API errors to RuntimeError."""
        mock_bitrix_api.post("crm.deal.delete").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Deal not found"},
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _crm_deal_delete(id=99999)

    @pytest.mark.asyncio
    async def test_crm_deal_delete_connection_error(self, setup_client, monkeypatch):
        """crm_deal_delete should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "crm_deal_delete", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _crm_deal_delete(id=410)


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
            priority="medium",
        )

        assert result["id"] == 457
        assert result["title"] == sample_task_data["title"]

        # Verify API was called with correct fields
        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        fields = body["fields"]

        assert fields["TITLE"] == sample_task_data["title"]
        assert fields["RESPONSIBLE_ID"] == sample_task_data["responsibleId"]
        assert fields["DESCRIPTION"] == sample_task_data["description"]
        assert fields["GROUP_ID"] == sample_task_data["groupId"]
        assert fields["PARENT_ID"] == sample_task_data["parentId"]
        assert fields["PRIORITY"] == 1

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


class TestTaskUpdate:
    """Tests for task_update tool."""

    @pytest.mark.asyncio
    async def test_task_update_basic_sends_fields(self, setup_client, mock_bitrix_api):
        """task_update should send correct payload and map status synonyms."""
        mock_bitrix_api.post("tasks.task.update").mock(
            return_value=Response(200, json={"result": True})
        )

        result = await _task_update(
            id=456,
            title="Updated title",
            description="Updated description",
            priority="high",
            status="in progress",
            responsibleId=7,
            accomplices=[8, 9],
            auditors=[10],
            deadline="2025-12-31T23:59:00+02:00",
            startDatePlan="2025-12-01T10:00:00+02:00",
            endDatePlan="2025-12-02T18:00:00+02:00",
            groupId=5,
            parentId=0,
            stageId=11,
        )

        assert result == {"id": 456, "updated": True}

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["taskId"] == 456
        fields = body["fields"]
        assert fields["TITLE"] == "Updated title"
        assert fields["DESCRIPTION"] == "Updated description"
        assert fields["PRIORITY"] == 2
        assert fields["STATUS"] == 3  # "in progress" -> in_progress -> 3
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
    async def test_task_update_status_done_maps_to_completed(self, setup_client, mock_bitrix_api):
        """task_update should map 'done' to completed status code."""
        mock_bitrix_api.post("tasks.task.update").mock(
            return_value=Response(200, json={"result": True})
        )

        await _task_update(id=456, status="done")

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["fields"]["STATUS"] == 5

    @pytest.mark.asyncio
    async def test_task_update_requires_at_least_one_field(self, setup_client):
        """task_update should require at least one updatable field."""
        with pytest.raises(RuntimeError, match="At least one field must be provided"):
            await _task_update(id=456)

    @pytest.mark.asyncio
    async def test_task_update_invalid_status_raises(self, setup_client):
        """task_update should reject unknown status strings."""
        with pytest.raises(RuntimeError, match="Unknown task status"):
            await _task_update(id=456, status="banana")

    @pytest.mark.asyncio
    async def test_task_update_invalid_priority_raises(self, setup_client):
        """task_update should reject unknown priority strings."""
        with pytest.raises(RuntimeError, match="Unknown task priority"):
            await _task_update(id=456, priority="banana")

    @pytest.mark.asyncio
    async def test_task_update_priority_int_raises(self, setup_client):
        """task_update should not accept numeric priority input (string-only API)."""
        with pytest.raises(RuntimeError, match="Unknown task priority"):
            await _task_update(id=456, priority=2)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_task_update_api_error(self, setup_client, api_error_response, mock_bitrix_api):
        """task_update should re-raise API errors as RuntimeError."""
        mock_bitrix_api.post("tasks.task.update").mock(
            return_value=Response(200, json=api_error_response)
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error"):
            await _task_update(id=456, title="Will fail")

    @pytest.mark.asyncio
    async def test_task_update_connection_error(self, setup_client, monkeypatch):
        """task_update should re-raise connection errors as RuntimeError."""
        client = get_client()

        async def _raise_connection_error(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            raise BitrixConnectionError("network down")

        monkeypatch.setattr(client, "task_update", _raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _task_update(id=456, title="Test")


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
        assert results[0]["parentId"] is None
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


class TestTaskStagesGet:
    """Tests for task_stages_get tool."""

    @pytest.mark.asyncio
    async def test_task_stages_get_basic(
        self,
        setup_client,
        sample_scrum_sprint_list_response,
        sample_scrum_kanban_get_stages_response,
        mock_bitrix_api,
    ):
        """task_stages_get should return formatted stages sorted by SORT."""
        mock_bitrix_api.post("tasks.api.scrum.sprint.list").mock(
            return_value=Response(200, json=sample_scrum_sprint_list_response)
        )
        mock_bitrix_api.post("tasks.api.scrum.kanban.getStages").mock(
            return_value=Response(200, json=sample_scrum_kanban_get_stages_response)
        )

        results = await _task_stages_get(entityId=5)

        assert len(results) == 3
        assert results[0]["id"] == 58
        assert results[0]["title"] == "To Do"
        assert results[0]["sprintId"] == 5
        assert results[1]["id"] == 59
        assert results[1]["title"] == "In Progress"
        assert results[2]["id"] == 60
        assert results[2]["title"] == "Done"

    @pytest.mark.asyncio
    async def test_task_stages_get_request_body(
        self,
        setup_client,
        sample_scrum_sprint_list_response,
        sample_scrum_kanban_get_stages_response,
        mock_bitrix_api,
    ):
        """task_stages_get should send correct parameters."""
        mock_bitrix_api.post("tasks.api.scrum.sprint.list").mock(
            return_value=Response(200, json=sample_scrum_sprint_list_response)
        )
        mock_bitrix_api.post("tasks.api.scrum.kanban.getStages").mock(
            return_value=Response(200, json=sample_scrum_kanban_get_stages_response)
        )

        await _task_stages_get(entityId=5)

        import json

        request_0 = mock_bitrix_api.calls[0].request
        body_0 = json.loads(request_0.content)
        assert body_0["filter"]["GROUP_ID"] == 5
        assert body_0["order"]["DATE_START"] == "DESC"

        request_1 = mock_bitrix_api.calls[1].request
        body_1 = json.loads(request_1.content)
        assert body_1["sprintId"] == 5


class TestTaskStagesMoveTask:
    """Tests for task_stages_move_task tool."""

    @pytest.mark.asyncio
    async def test_task_stages_move_task_basic(self, setup_client, mock_bitrix_api):
        """task_stages_move_task should move a task to the target stage."""
        mock_bitrix_api.post("task.stages.movetask").mock(
            return_value=Response(200, json={"result": True})
        )

        result = await _task_stages_move_task(id=456, stageId=12)

        assert result["id"] == 456
        assert result["stageId"] == 12
        assert result["moved"] is True

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 456
        assert body["stageId"] == 12

    @pytest.mark.asyncio
    async def test_task_stages_move_task_with_before(self, setup_client, mock_bitrix_api):
        """task_stages_move_task should pass the `before` parameter when provided."""
        mock_bitrix_api.post("task.stages.movetask").mock(
            return_value=Response(200, json={"result": True})
        )

        result = await _task_stages_move_task(id=456, stageId=12, before=789)

        assert result["before"] == 789

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["before"] == 789
        assert "after" not in body

    @pytest.mark.asyncio
    async def test_task_stages_move_task_before_after_exclusive(
        self, setup_client, mock_bitrix_api
    ):
        """task_stages_move_task should reject when both before and after are provided."""
        with pytest.raises(RuntimeError):
            await _task_stages_move_task(id=1, stageId=2, before=3, after=4)


class TestScrumBacklogTasks:
    """Tests for scrum_backlog_tasks tool."""

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_returns_metadata_and_tasks(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        sample_task_list_backlog_page_1_response,
        sample_task_list_backlog_page_2_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should return backlog metadata and aggregated tasks."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            side_effect=[
                Response(200, json=sample_task_list_backlog_page_1_response),
                Response(200, json=sample_task_list_backlog_page_2_response),
            ]
        )

        result = await _scrum_backlog_tasks(groupId=205)

        assert result["groupId"] == 205
        assert result["backlogId"] == 91
        assert result["count"] == 2
        assert len(result["tasks"]) == 2
        assert result["tasks"][0]["id"] == 456
        assert result["tasks"][1]["id"] == 789

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_multi_page_aggregation(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        sample_task_list_backlog_page_1_response,
        sample_task_list_backlog_page_2_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should iterate pages until next cursor is absent."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            side_effect=[
                Response(200, json=sample_task_list_backlog_page_1_response),
                Response(200, json=sample_task_list_backlog_page_2_response),
            ]
        )

        result = await _scrum_backlog_tasks(groupId=205)

        assert result["count"] == 2
        assert mock_bitrix_api.calls.call_count == 3
        assert mock_bitrix_api.calls[1].request.url.path.endswith("tasks.task.list")
        assert mock_bitrix_api.calls[2].request.url.path.endswith("tasks.task.list")

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_sends_group_and_backlog_filters(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        sample_task_list_backlog_page_1_response,
        sample_task_list_backlog_page_2_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should include GROUP_ID and BACKLOG_ID in task list filter."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            side_effect=[
                Response(200, json=sample_task_list_backlog_page_1_response),
                Response(200, json=sample_task_list_backlog_page_2_response),
            ]
        )

        await _scrum_backlog_tasks(groupId=205)

        import json

        first_page_body = json.loads(mock_bitrix_api.calls[1].request.content)
        second_page_body = json.loads(mock_bitrix_api.calls[2].request.content)

        assert first_page_body["filter"]["GROUP_ID"] == 205
        assert first_page_body["filter"]["BACKLOG_ID"] == 91
        assert "%TITLE" not in first_page_body["filter"]
        assert "STATUS" not in first_page_body["filter"]
        assert "RESPONSIBLE_ID" not in first_page_body["filter"]
        assert first_page_body["start"] == 0
        assert second_page_body["filter"]["GROUP_ID"] == 205
        assert second_page_body["filter"]["BACKLOG_ID"] == 91
        assert "%TITLE" not in second_page_body["filter"]
        assert "STATUS" not in second_page_body["filter"]
        assert "RESPONSIBLE_ID" not in second_page_body["filter"]
        assert second_page_body["start"] == 50

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_query_filter_maps_to_title(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        sample_task_list_backlog_page_2_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should map query to %TITLE in task list filter."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_backlog_page_2_response)
        )

        await _scrum_backlog_tasks(groupId=205, query="welcome")

        import json

        request_body = json.loads(mock_bitrix_api.calls[1].request.content)
        assert request_body["filter"]["%TITLE"] == "welcome"

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_status_filter_maps_to_code(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        sample_task_list_backlog_page_2_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should map status string to STATUS code in task list filter."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_backlog_page_2_response)
        )

        await _scrum_backlog_tasks(groupId=205, status="in progress")

        import json

        request_body = json.loads(mock_bitrix_api.calls[1].request.content)
        assert request_body["filter"]["STATUS"] == 3

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_responsible_filter_maps_to_id(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        sample_task_list_backlog_page_2_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should map responsibleId to RESPONSIBLE_ID in task list filter."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_backlog_page_2_response)
        )

        await _scrum_backlog_tasks(groupId=205, responsibleId=7)

        import json

        request_body = json.loads(mock_bitrix_api.calls[1].request.content)
        assert request_body["filter"]["RESPONSIBLE_ID"] == 7

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_combined_filters_sent_together(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        sample_task_list_backlog_page_2_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should send query, status, and responsible filters together."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json=sample_task_list_backlog_page_2_response)
        )

        await _scrum_backlog_tasks(
            groupId=205,
            query="welcome",
            status="in_progress",
            responsibleId=7,
        )

        import json

        request_body = json.loads(mock_bitrix_api.calls[1].request.content)
        filter_payload = request_body["filter"]
        assert filter_payload["GROUP_ID"] == 205
        assert filter_payload["BACKLOG_ID"] == 91
        assert filter_payload["%TITLE"] == "welcome"
        assert filter_payload["STATUS"] == 3
        assert filter_payload["RESPONSIBLE_ID"] == 7

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_invalid_status_raises_runtime_error(
        self,
        setup_client,
        sample_scrum_backlog_get_response,
        mock_bitrix_api,
    ):
        """scrum_backlog_tasks should reject unknown status strings."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )

        with pytest.raises(RuntimeError, match="Unknown task status"):
            await _scrum_backlog_tasks(groupId=205, status="banana")

        assert mock_bitrix_api.calls.call_count == 1

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_empty_backlog_returns_empty_list(
        self, setup_client, sample_scrum_backlog_get_response, mock_bitrix_api
    ):
        """scrum_backlog_tasks should return count=0 and tasks=[] for empty backlog."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(200, json=sample_scrum_backlog_get_response)
        )
        mock_bitrix_api.post("tasks.task.list").mock(
            return_value=Response(200, json={"result": {"tasks": []}, "total": 0})
        )

        result = await _scrum_backlog_tasks(groupId=205)

        assert result["groupId"] == 205
        assert result["backlogId"] == 91
        assert result["count"] == 0
        assert result["tasks"] == []

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_connection_error_mapping(self, setup_client, monkeypatch):
        """scrum_backlog_tasks should map connection errors to RuntimeError."""
        client = get_client()

        async def raise_connection_error(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            raise BitrixConnectionError("Network timeout")

        monkeypatch.setattr(client, "scrum_backlog_get", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to connect to Bitrix24"):
            await _scrum_backlog_tasks(groupId=205)

    @pytest.mark.asyncio
    async def test_scrum_backlog_tasks_api_error_mapping(self, setup_client, mock_bitrix_api):
        """scrum_backlog_tasks should map API errors to RuntimeError."""
        mock_bitrix_api.post("tasks.api.scrum.backlog.get").mock(
            return_value=Response(
                200,
                json={
                    "error": "ERROR_CORE",
                    "error_description": "Backlog not found",
                },
            )
        )

        with pytest.raises(RuntimeError, match="Bitrix24 API error:"):
            await _scrum_backlog_tasks(groupId=205)


class TestScrumEpicList:
    """Tests for scrum_epic_list tool."""

    @pytest.mark.asyncio
    async def test_scrum_epic_list_basic(
        self, setup_client, sample_scrum_epic_list_response, mock_bitrix_api
    ):
        """scrum_epic_list should return formatted epics."""
        mock_bitrix_api.post("tasks.api.scrum.epic.list").mock(
            return_value=Response(200, json=sample_scrum_epic_list_response)
        )

        results = await _scrum_epic_list(groupId=5)

        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[0]["groupId"] == 5
        assert results[0]["name"] == "Dashboard"

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["filter"]["GROUP_ID"] == 5
        assert body["order"]["ID"] == "asc"
        assert body["start"] == 0
        assert "NAME" in body["select"]

    @pytest.mark.asyncio
    async def test_scrum_epic_list_query_filters(
        self, setup_client, sample_scrum_epic_list_response, mock_bitrix_api
    ):
        """scrum_epic_list should filter by query (substring match)."""
        mock_bitrix_api.post("tasks.api.scrum.epic.list").mock(
            return_value=Response(200, json=sample_scrum_epic_list_response)
        )

        results = await _scrum_epic_list(groupId=5, query="dash")

        assert len(results) == 1
        assert results[0]["name"] == "Dashboard"


class TestScrumTaskGet:
    """Tests for scrum_task_get tool."""

    @pytest.mark.asyncio
    async def test_scrum_task_get_basic(
        self, setup_client, sample_scrum_task_get_response, mock_bitrix_api
    ):
        """scrum_task_get should return Scrum fields for a task."""
        mock_bitrix_api.post("tasks.api.scrum.task.get").mock(
            return_value=Response(200, json=sample_scrum_task_get_response)
        )

        result = await _scrum_task_get(id=456)

        assert result["id"] == 456
        assert result["entityId"] == 2
        assert result["storyPoints"] == "2"
        assert result["epicId"] == 1

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 456


class TestScrumTaskUpdate:
    """Tests for scrum_task_update tool."""

    @pytest.mark.asyncio
    async def test_scrum_task_update_by_epic_id(
        self, setup_client, sample_scrum_task_update_response, mock_bitrix_api
    ):
        """scrum_task_update should send correct payload when epicId is provided."""
        mock_bitrix_api.post("tasks.api.scrum.task.update").mock(
            return_value=Response(200, json=sample_scrum_task_update_response)
        )

        result = await _scrum_task_update(id=456, epicId=1, storyPoints="8", entityId=2, sort=10)

        assert result["id"] == 456
        assert result["updated"] is True
        assert result["epicId"] == 1
        assert result["storyPoints"] == "8"
        assert result["entityId"] == 2
        assert result["sort"] == 10

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 456
        assert body["fields"]["entityId"] == 2
        assert body["fields"]["storyPoints"] == "8"
        assert body["fields"]["epicId"] == 1
        assert body["fields"]["sort"] == 10

    @pytest.mark.asyncio
    async def test_scrum_task_update_accepts_boolean_result(self, setup_client, mock_bitrix_api):
        """scrum_task_update should work when Bitrix24 returns a bare boolean result."""
        mock_bitrix_api.post("tasks.api.scrum.task.update").mock(
            return_value=Response(200, json={"result": True})
        )

        result = await _scrum_task_update(id=456, epicId=1)

        assert result["id"] == 456
        assert result["updated"] is True
        assert result["epicId"] == 1

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 456
        assert body["fields"]["epicId"] == 1

    @pytest.mark.asyncio
    async def test_scrum_task_update_by_epic_name_resolves(
        self,
        setup_client,
        sample_task_get_response,
        sample_scrum_epic_list_response,
        sample_scrum_task_update_response,
        mock_bitrix_api,
    ):
        """scrum_task_update should resolve epicName using task.groupId and epic list."""
        mock_bitrix_api.post("tasks.task.get").mock(
            return_value=Response(200, json=sample_task_get_response)
        )
        mock_bitrix_api.post("tasks.api.scrum.epic.list").mock(
            return_value=Response(200, json=sample_scrum_epic_list_response)
        )
        mock_bitrix_api.post("tasks.api.scrum.task.update").mock(
            return_value=Response(200, json=sample_scrum_task_update_response)
        )

        result = await _scrum_task_update(id=456, epicName="Dashboard", storyPoints="3")

        assert result["updated"] is True
        assert result["epicId"] == 1
        assert result["epicName"] == "Dashboard"
        assert result["storyPoints"] == "3"

        assert mock_bitrix_api.calls[0].request.url.path.endswith("tasks.task.get")
        assert mock_bitrix_api.calls[1].request.url.path.endswith("tasks.api.scrum.epic.list")
        assert mock_bitrix_api.calls[2].request.url.path.endswith("tasks.api.scrum.task.update")

        import json

        update_body = json.loads(mock_bitrix_api.calls[2].request.content)
        assert update_body["id"] == 456
        assert update_body["fields"]["epicId"] == 1
        assert update_body["fields"]["storyPoints"] == "3"

    @pytest.mark.asyncio
    async def test_scrum_task_update_ambiguous_epic_name_raises(
        self, setup_client, sample_task_get_response, mock_bitrix_api
    ):
        """scrum_task_update should raise on ambiguous epicName and not call update."""
        mock_bitrix_api.post("tasks.task.get").mock(
            return_value=Response(200, json=sample_task_get_response)
        )
        mock_bitrix_api.post("tasks.api.scrum.epic.list").mock(
            return_value=Response(
                200,
                json={
                    "result": [
                        {"id": 1, "groupId": 5, "name": "Dashboard"},
                        {"id": 2, "groupId": 5, "name": "Dashboard v2"},
                    ]
                },
            )
        )

        with pytest.raises(RuntimeError, match="Ambiguous epicName"):
            await _scrum_task_update(id=456, epicName="Dash")


class TestScrumTaskCreate:
    """Tests for scrum_task_create tool."""

    @pytest.mark.asyncio
    async def test_scrum_task_create_with_epic_name(
        self,
        setup_client,
        sample_scrum_epic_list_response,
        sample_task_add_response,
        sample_scrum_task_update_response,
        mock_bitrix_api,
    ):
        """scrum_task_create should resolve epicName, create task, then update scrum fields."""
        mock_bitrix_api.post("tasks.api.scrum.epic.list").mock(
            return_value=Response(200, json=sample_scrum_epic_list_response)
        )
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )
        mock_bitrix_api.post("tasks.api.scrum.task.update").mock(
            return_value=Response(200, json=sample_scrum_task_update_response)
        )

        result = await _scrum_task_create(
            title="New scrum task",
            responsibleId=7,
            groupId=5,
            epicName="CMS",
            storyPoints="5",
            priority="high",
        )

        assert result["id"] == 457
        assert result["created"] is True
        assert result["scrumUpdated"] is True
        assert result["epicId"] == 2
        assert result["epicName"] == "CMS"
        assert result["storyPoints"] == "5"
        assert result["groupId"] == 5

        assert mock_bitrix_api.calls[0].request.url.path.endswith("tasks.api.scrum.epic.list")
        assert mock_bitrix_api.calls[1].request.url.path.endswith("tasks.task.add")
        assert mock_bitrix_api.calls[2].request.url.path.endswith("tasks.api.scrum.task.update")

        import json

        add_body = json.loads(mock_bitrix_api.calls[1].request.content)
        assert add_body["fields"]["TITLE"] == "New scrum task"
        assert add_body["fields"]["RESPONSIBLE_ID"] == 7
        assert add_body["fields"]["GROUP_ID"] == 5
        assert add_body["fields"]["PRIORITY"] == 2

        update_body = json.loads(mock_bitrix_api.calls[2].request.content)
        assert update_body["id"] == 457
        assert update_body["fields"]["epicId"] == 2
        assert update_body["fields"]["storyPoints"] == "5"

    @pytest.mark.asyncio
    async def test_scrum_task_create_without_scrum_fields_still_updates(
        self,
        setup_client,
        sample_task_add_response,
        sample_scrum_task_update_response,
        mock_bitrix_api,
    ):
        """scrum_task_create should still call scrum update (with empty fields) to link to Scrum."""
        mock_bitrix_api.post("tasks.task.add").mock(
            return_value=Response(200, json=sample_task_add_response)
        )
        mock_bitrix_api.post("tasks.api.scrum.task.update").mock(
            return_value=Response(200, json=sample_scrum_task_update_response)
        )

        result = await _scrum_task_create(title="No scrum fields", responsibleId=7, groupId=5)

        assert result["id"] == 457
        assert result["scrumUpdated"] is True

        import json

        update_body = json.loads(mock_bitrix_api.calls[1].request.content)
        assert update_body["id"] == 457
        assert update_body["fields"] == {}
