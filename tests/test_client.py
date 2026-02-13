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


class TestCrmLeadGet:
    """Tests for crm_lead_get method."""

    @pytest.mark.asyncio
    async def test_crm_lead_get_success(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_get should return parsed lead details."""
        response = {
            "result": {
                "ID": "610",
                "TITLE": "Lead from Website",
                "STATUS_ID": "NEW",
                "OPENED": "Y",
                "ASSIGNED_BY_ID": "1",
                "COMPANY_ID": "9",
                "CONTACT_ID": "84",
                "SOURCE_ID": "WEB",
                "COMMENTS": "Interested in annual plan",
                "UF_CRM_1721244482250": "Custom value",
                "IS_RETURN_CUSTOMER": "N",
            }
        }
        mock_bitrix_api.post("crm.lead.get").mock(return_value=Response(200, json=response))

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            lead = await client.crm_lead_get(lead_id=610)

        assert lead.id == "610"
        assert lead.title == "Lead from Website"
        assert lead.status_id == "NEW"
        assert lead.contact_id == "84"
        assert lead.model_extra is not None
        assert lead.model_extra.get("UF_CRM_1721244482250") == "Custom value"
        assert lead.model_extra.get("IS_RETURN_CUSTOMER") == "N"

    @pytest.mark.asyncio
    async def test_crm_lead_get_sends_id_param(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_get should send correct id payload."""
        mock_bitrix_api.post("crm.lead.get").mock(
            return_value=Response(200, json={"result": {"ID": "610", "TITLE": "Lead"}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_lead_get(lead_id=610)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 610

    @pytest.mark.asyncio
    async def test_crm_lead_get_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_get should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.lead.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Lead not found"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Lead not found"):
                await client.crm_lead_get(lead_id=99999)

    @pytest.mark.asyncio
    async def test_crm_lead_get_empty_result_raises(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_get should raise BitrixAPIError when result is empty."""
        mock_bitrix_api.post("crm.lead.get").mock(return_value=Response(200, json={"result": {}}))

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Lead 610 not found"):
                await client.crm_lead_get(lead_id=610)

    @pytest.mark.asyncio
    async def test_crm_lead_get_unexpected_result_raises(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_get should raise BitrixAPIError on unexpected result shape."""
        mock_bitrix_api.post("crm.lead.get").mock(
            return_value=Response(200, json={"result": ["not-a-dict"]})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Unexpected response format"):
                await client.crm_lead_get(lead_id=610)


class TestCrmLeadList:
    """Tests for crm_lead_list method."""

    @pytest.mark.asyncio
    async def test_crm_lead_list_success(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_list should return leads and pagination metadata."""
        response = {
            "result": [
                {
                    "ID": "610",
                    "TITLE": "Lead from Website",
                    "STATUS_ID": "NEW",
                    "ASSIGNED_BY_ID": "1",
                    "CONTACT_ID": "84",
                    "UF_CRM_1721244482250": "Custom value",
                },
                {
                    "ID": "611",
                    "TITLE": "Inbound Call Lead",
                    "STATUS_ID": "IN_PROCESS",
                    "ASSIGNED_BY_ID": "6",
                    "CONTACT_ID": "85",
                },
            ],
            "total": 95,
            "next": 50,
        }
        mock_bitrix_api.post("crm.lead.list").mock(return_value=Response(200, json=response))

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            result = await client.crm_lead_list(
                filter={"STATUS_ID": "NEW"},
                order={"DATE_CREATE": "DESC"},
                select=["ID", "TITLE", "STATUS_ID"],
                start=0,
            )

        assert len(result["items"]) == 2
        assert result["items"][0]["ID"] == "610"
        assert result["items"][0]["UF_CRM_1721244482250"] == "Custom value"
        assert result["total"] == 95
        assert result["next"] == 50

    @pytest.mark.asyncio
    async def test_crm_lead_list_sends_payload(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_list should send filter/order/select/start payload."""
        mock_bitrix_api.post("crm.lead.list").mock(
            return_value=Response(200, json={"result": [], "total": 0})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_lead_list(
                filter={"STATUS_ID": "IN_PROCESS"},
                order={"TITLE": "ASC"},
                select=["ID", "TITLE", "DATE_CREATE"],
                start=100,
            )

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["filter"] == {"STATUS_ID": "IN_PROCESS"}
        assert body["order"] == {"TITLE": "ASC"}
        assert body["select"] == ["ID", "TITLE", "DATE_CREATE"]
        assert body["start"] == 100

    @pytest.mark.asyncio
    async def test_crm_lead_list_without_total_or_next(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_list should tolerate missing total/next in response."""
        mock_bitrix_api.post("crm.lead.list").mock(
            return_value=Response(
                200,
                json={"result": [{"ID": "610", "TITLE": "Lead from Website"}]},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            result = await client.crm_lead_list()

        assert len(result["items"]) == 1
        assert result["total"] is None
        assert result["next"] is None

    @pytest.mark.asyncio
    async def test_crm_lead_list_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_list should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.lead.list").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Access denied"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Access denied"):
                await client.crm_lead_list()

    @pytest.mark.asyncio
    async def test_crm_lead_list_unexpected_result_raises(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_list should raise BitrixAPIError on unexpected result shape."""
        mock_bitrix_api.post("crm.lead.list").mock(
            return_value=Response(200, json={"result": {"ID": "610"}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Unexpected response format"):
                await client.crm_lead_list()


class TestCrmLeadProductRowsGet:
    """Tests for crm_lead_productrows_get method."""

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_success(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_productrows_get should return product row list."""
        response = {
            "result": [
                {
                    "ID": "901",
                    "PRODUCT_ID": "101",
                    "PRODUCT_NAME": "Starter Plan",
                    "PRICE": "99.00",
                    "QUANTITY": "1",
                },
                {
                    "ID": "902",
                    "PRODUCT_ID": "102",
                    "PRODUCT_NAME": "Onboarding Package",
                    "PRICE": "250.00",
                    "QUANTITY": "1",
                },
            ]
        }
        mock_bitrix_api.post("crm.lead.productrows.get").mock(
            return_value=Response(200, json=response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            rows = await client.crm_lead_productrows_get(lead_id=610)

        assert len(rows) == 2
        assert rows[0]["PRODUCT_ID"] == "101"
        assert rows[1]["PRODUCT_NAME"] == "Onboarding Package"

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_sends_id_param(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_productrows_get should send correct id payload."""
        mock_bitrix_api.post("crm.lead.productrows.get").mock(
            return_value=Response(200, json={"result": []})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_lead_productrows_get(lead_id=610)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 610

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_empty_rows(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_productrows_get should return an empty list when no rows exist."""
        mock_bitrix_api.post("crm.lead.productrows.get").mock(
            return_value=Response(200, json={"result": []})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            rows = await client.crm_lead_productrows_get(lead_id=610)

        assert rows == []

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_productrows_get should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.lead.productrows.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Lead not found"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Lead not found"):
                await client.crm_lead_productrows_get(lead_id=99999)

    @pytest.mark.asyncio
    async def test_crm_lead_productrows_get_unexpected_result_raises(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """crm_lead_productrows_get should raise on unexpected result shape."""
        mock_bitrix_api.post("crm.lead.productrows.get").mock(
            return_value=Response(200, json={"result": {"ID": "901"}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Unexpected response format"):
                await client.crm_lead_productrows_get(lead_id=610)


class TestCrmLeadAdd:
    """Tests for crm_lead_add method."""

    @pytest.mark.asyncio
    async def test_crm_lead_add_success(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_add should return created lead ID."""
        mock_bitrix_api.post("crm.lead.add").mock(return_value=Response(200, json={"result": 612}))

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            lead_id = await client.crm_lead_add(fields={"TITLE": "New Lead"})

        assert lead_id == 612

    @pytest.mark.asyncio
    async def test_crm_lead_add_sends_fields_and_params_payload(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """crm_lead_add should send fields and params payload."""
        mock_bitrix_api.post("crm.lead.add").mock(return_value=Response(200, json={"result": 612}))

        fields = {
            "TITLE": "Lead from Website",
            "STATUS_ID": "NEW",
            "OPPORTUNITY": "1200.00",
            "CURRENCY_ID": "USD",
        }
        params = {"REGISTER_SONET_EVENT": "Y"}

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_lead_add(fields=fields, params=params)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["fields"] == fields
        assert body["params"] == params

    @pytest.mark.asyncio
    async def test_crm_lead_add_requires_non_empty_fields(self, mock_webhook_url):
        """crm_lead_add should reject empty fields."""
        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(ValueError, match="must not be empty"):
                await client.crm_lead_add(fields={})

    @pytest.mark.asyncio
    async def test_crm_lead_add_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_add should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.lead.add").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Access denied"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Access denied"):
                await client.crm_lead_add(fields={"TITLE": "Blocked Lead"})


class TestCrmLeadUpdate:
    """Tests for crm_lead_update method."""

    @pytest.mark.asyncio
    async def test_crm_lead_update_success(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_update should return update status."""
        mock_bitrix_api.post("crm.lead.update").mock(
            return_value=Response(200, json={"result": True})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            updated = await client.crm_lead_update(
                lead_id=610,
                fields={"TITLE": "Updated Lead Title"},
            )

        assert updated is True

    @pytest.mark.asyncio
    async def test_crm_lead_update_sends_payload(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_update should send id, fields, and optional params payload."""
        mock_bitrix_api.post("crm.lead.update").mock(
            return_value=Response(200, json={"result": True})
        )

        fields = {
            "TITLE": "Updated Lead Title",
            "STATUS_ID": "IN_PROCESS",
            "OPPORTUNITY": "2400.00",
        }
        params = {"REGISTER_SONET_EVENT": "N"}

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_lead_update(lead_id=610, fields=fields, params=params)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 610
        assert body["fields"] == fields
        assert body["params"] == params

    @pytest.mark.asyncio
    async def test_crm_lead_update_requires_non_empty_fields(self, mock_webhook_url):
        """crm_lead_update should reject empty fields."""
        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(ValueError, match="must not be empty"):
                await client.crm_lead_update(lead_id=610, fields={})

    @pytest.mark.asyncio
    async def test_crm_lead_update_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_update should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.lead.update").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Update denied"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Update denied"):
                await client.crm_lead_update(lead_id=610, fields={"TITLE": "Blocked"})

    @pytest.mark.asyncio
    async def test_crm_lead_update_unexpected_result_raises(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """crm_lead_update should raise BitrixAPIError on unexpected result shape."""
        mock_bitrix_api.post("crm.lead.update").mock(
            return_value=Response(200, json={"result": {"status": "ok"}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Unexpected response format"):
                await client.crm_lead_update(lead_id=610, fields={"TITLE": "Updated"})


class TestCrmLeadDelete:
    """Tests for crm_lead_delete method."""

    @pytest.mark.asyncio
    async def test_crm_lead_delete_success(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_delete should return delete status."""
        mock_bitrix_api.post("crm.lead.delete").mock(
            return_value=Response(200, json={"result": True})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            deleted = await client.crm_lead_delete(lead_id=610)

        assert deleted is True

    @pytest.mark.asyncio
    async def test_crm_lead_delete_sends_id_payload(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_delete should send id payload."""
        mock_bitrix_api.post("crm.lead.delete").mock(
            return_value=Response(200, json={"result": True})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_lead_delete(lead_id=610)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 610

    @pytest.mark.asyncio
    async def test_crm_lead_delete_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_lead_delete should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.lead.delete").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Lead not found"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Lead not found"):
                await client.crm_lead_delete(lead_id=99999)


class TestCrmDealGet:
    """Tests for crm_deal_get method."""

    @pytest.mark.asyncio
    async def test_crm_deal_get_success(
        self, mock_webhook_url, sample_crm_deal_get_response, mock_bitrix_api
    ):
        """crm_deal_get should return parsed deal details."""
        mock_bitrix_api.post("crm.deal.get").mock(
            return_value=Response(200, json=sample_crm_deal_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            deal = await client.crm_deal_get(deal_id=410)

        assert deal.id == "410"
        assert deal.title == "New Deal #1"
        assert deal.stage_id == "PREPARATION"
        assert deal.currency_id == "EUR"
        assert deal.model_extra is not None
        assert deal.model_extra.get("UF_CRM_1721244482250") == "Hello world!"
        assert deal.model_extra.get("PARENT_ID_153") == "22"

    @pytest.mark.asyncio
    async def test_crm_deal_get_sends_id_param(
        self, mock_webhook_url, sample_crm_deal_get_response, mock_bitrix_api
    ):
        """crm_deal_get should send correct id payload."""
        mock_bitrix_api.post("crm.deal.get").mock(
            return_value=Response(200, json=sample_crm_deal_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_deal_get(deal_id=410)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 410

    @pytest.mark.asyncio
    async def test_crm_deal_get_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_get should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.deal.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Not found"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Not found"):
                await client.crm_deal_get(deal_id=99999)

    @pytest.mark.asyncio
    async def test_crm_deal_get_empty_result_raises(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_get should raise BitrixAPIError when result is empty."""
        mock_bitrix_api.post("crm.deal.get").mock(return_value=Response(200, json={"result": {}}))

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Deal 410 not found"):
                await client.crm_deal_get(deal_id=410)


class TestCrmDealFields:
    """Tests for crm_deal_fields method."""

    @pytest.mark.asyncio
    async def test_crm_deal_fields_success(
        self, mock_webhook_url, sample_crm_deal_fields_response, mock_bitrix_api
    ):
        """crm_deal_fields should return field metadata map."""
        mock_bitrix_api.post("crm.deal.fields").mock(
            return_value=Response(200, json=sample_crm_deal_fields_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            fields = await client.crm_deal_fields()

        assert "ID" in fields
        assert "TITLE" in fields
        assert "CONTACT_ID" in fields
        assert fields["CONTACT_ID"]["type"] == "crm_contact"

    @pytest.mark.asyncio
    async def test_crm_deal_fields_sends_empty_payload(
        self, mock_webhook_url, sample_crm_deal_fields_response, mock_bitrix_api
    ):
        """crm_deal_fields should send an empty object payload."""
        mock_bitrix_api.post("crm.deal.fields").mock(
            return_value=Response(200, json=sample_crm_deal_fields_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_deal_fields()

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body == {}

    @pytest.mark.asyncio
    async def test_crm_deal_fields_unexpected_result_raises(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """crm_deal_fields should raise BitrixAPIError on unexpected result shape."""
        mock_bitrix_api.post("crm.deal.fields").mock(
            return_value=Response(200, json={"result": []})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Unexpected response format"):
                await client.crm_deal_fields()

    @pytest.mark.asyncio
    async def test_crm_deal_fields_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_fields should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.deal.fields").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Access denied"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Access denied"):
                await client.crm_deal_fields()


class TestCrmDealList:
    """Tests for crm_deal_list method."""

    @pytest.mark.asyncio
    async def test_crm_deal_list_success(
        self, mock_webhook_url, sample_crm_deal_list_response, mock_bitrix_api
    ):
        """crm_deal_list should return deals and pagination metadata."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(200, json=sample_crm_deal_list_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            result = await client.crm_deal_list(
                filter={"CATEGORY_ID": 1},
                order={"TITLE": "ASC"},
                select=["ID", "TITLE", "STAGE_ID"],
                start=50,
            )

        assert len(result["items"]) == 2
        assert result["items"][0]["ID"] == "410"
        assert result["items"][0]["UF_CRM_1721244482250"] == "Hello world!"
        assert result["items"][0]["CONTACT_ID"] == "84"
        assert result["total"] == 120
        assert result["next"] == 50

    @pytest.mark.asyncio
    async def test_crm_deal_list_sends_payload(
        self, mock_webhook_url, sample_crm_deal_list_response, mock_bitrix_api
    ):
        """crm_deal_list should send filter/order/select/start payload."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(200, json=sample_crm_deal_list_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_deal_list(
                filter={"STAGE_ID": "C1:NEW"},
                order={"DATE_CREATE": "DESC"},
                select=["ID", "TITLE", "DATE_CREATE"],
                start=100,
            )

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["filter"] == {"STAGE_ID": "C1:NEW"}
        assert body["order"] == {"DATE_CREATE": "DESC"}
        assert body["select"] == ["ID", "TITLE", "DATE_CREATE"]
        assert body["start"] == 100

    @pytest.mark.asyncio
    async def test_crm_deal_list_without_next(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_list should tolerate missing total/next in response."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(
                200,
                json={"result": [{"ID": "410", "TITLE": "New Deal #1"}]},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            result = await client.crm_deal_list()

        assert len(result["items"]) == 1
        assert result["total"] is None
        assert result["next"] is None

    @pytest.mark.asyncio
    async def test_crm_deal_list_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_list should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Not found"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Not found"):
                await client.crm_deal_list()

    @pytest.mark.asyncio
    async def test_crm_deal_list_unexpected_result_raises(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_list should raise BitrixAPIError on unexpected result shape."""
        mock_bitrix_api.post("crm.deal.list").mock(
            return_value=Response(200, json={"result": {"ID": "410"}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Unexpected response format"):
                await client.crm_deal_list()


class TestCrmDealProductRowsGet:
    """Tests for crm_deal_productrows_get method."""

    @pytest.mark.asyncio
    async def test_crm_deal_productrows_get_success(
        self, mock_webhook_url, sample_crm_deal_productrows_get_response, mock_bitrix_api
    ):
        """crm_deal_productrows_get should return product row list."""
        mock_bitrix_api.post("crm.deal.productrows.get").mock(
            return_value=Response(200, json=sample_crm_deal_productrows_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            rows = await client.crm_deal_productrows_get(deal_id=410)

        assert len(rows) == 2
        assert rows[0]["PRODUCT_ID"] == "101"
        assert rows[0]["PRODUCT_NAME"] == "Website Subscription"
        assert rows[1]["PRODUCT_ID"] == "102"

    @pytest.mark.asyncio
    async def test_crm_deal_productrows_get_sends_id_param(
        self, mock_webhook_url, sample_crm_deal_productrows_get_response, mock_bitrix_api
    ):
        """crm_deal_productrows_get should send correct id payload."""
        mock_bitrix_api.post("crm.deal.productrows.get").mock(
            return_value=Response(200, json=sample_crm_deal_productrows_get_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_deal_productrows_get(deal_id=410)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 410

    @pytest.mark.asyncio
    async def test_crm_deal_productrows_get_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_productrows_get should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.deal.productrows.get").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Deal not found"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Deal not found"):
                await client.crm_deal_productrows_get(deal_id=99999)

    @pytest.mark.asyncio
    async def test_crm_deal_productrows_get_unexpected_result_raises(
        self, mock_webhook_url, mock_bitrix_api
    ):
        """crm_deal_productrows_get should raise on unexpected result shape."""
        mock_bitrix_api.post("crm.deal.productrows.get").mock(
            return_value=Response(200, json={"result": {"ID": "120"}})
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Unexpected response format"):
                await client.crm_deal_productrows_get(deal_id=410)


class TestCrmDealAdd:
    """Tests for crm_deal_add method."""

    @pytest.mark.asyncio
    async def test_crm_deal_add_success(
        self, mock_webhook_url, sample_crm_deal_add_response, mock_bitrix_api
    ):
        """crm_deal_add should return created deal ID."""
        mock_bitrix_api.post("crm.deal.add").mock(
            return_value=Response(200, json=sample_crm_deal_add_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            deal_id = await client.crm_deal_add(fields={"TITLE": "New Deal"})

        assert deal_id == 512

    @pytest.mark.asyncio
    async def test_crm_deal_add_sends_fields_payload(
        self, mock_webhook_url, sample_crm_deal_add_response, mock_bitrix_api
    ):
        """crm_deal_add should send fields payload as-is."""
        mock_bitrix_api.post("crm.deal.add").mock(
            return_value=Response(200, json=sample_crm_deal_add_response)
        )

        fields = {
            "TITLE": "New Deal #2",
            "STAGE_ID": "NEW",
            "OPPORTUNITY": "1500.00",
            "CURRENCY_ID": "USD",
        }

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_deal_add(fields=fields)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["fields"] == fields

    @pytest.mark.asyncio
    async def test_crm_deal_add_requires_non_empty_fields(self, mock_webhook_url):
        """crm_deal_add should reject empty fields."""
        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(ValueError, match="must not be empty"):
                await client.crm_deal_add(fields={})

    @pytest.mark.asyncio
    async def test_crm_deal_add_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_add should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.deal.add").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Access denied"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Access denied"):
                await client.crm_deal_add(fields={"TITLE": "Blocked Deal"})


class TestCrmDealUpdate:
    """Tests for crm_deal_update method."""

    @pytest.mark.asyncio
    async def test_crm_deal_update_success(
        self, mock_webhook_url, sample_crm_deal_update_response, mock_bitrix_api
    ):
        """crm_deal_update should return update status."""
        mock_bitrix_api.post("crm.deal.update").mock(
            return_value=Response(200, json=sample_crm_deal_update_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            updated = await client.crm_deal_update(
                deal_id=410,
                fields={"TITLE": "Updated Deal Title"},
            )

        assert updated is True

    @pytest.mark.asyncio
    async def test_crm_deal_update_sends_payload(
        self, mock_webhook_url, sample_crm_deal_update_response, mock_bitrix_api
    ):
        """crm_deal_update should send id and fields payload."""
        mock_bitrix_api.post("crm.deal.update").mock(
            return_value=Response(200, json=sample_crm_deal_update_response)
        )

        fields = {
            "TITLE": "Updated Deal Title",
            "STAGE_ID": "PREPAYMENT_INVOICE",
            "OPPORTUNITY": "2000.00",
        }

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_deal_update(deal_id=410, fields=fields)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 410
        assert body["fields"] == fields

    @pytest.mark.asyncio
    async def test_crm_deal_update_requires_valid_id(self, mock_webhook_url):
        """crm_deal_update should reject non-positive deal IDs."""
        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(ValueError, match="greater than 0"):
                await client.crm_deal_update(deal_id=0, fields={"TITLE": "Invalid"})

    @pytest.mark.asyncio
    async def test_crm_deal_update_requires_non_empty_fields(self, mock_webhook_url):
        """crm_deal_update should reject empty fields."""
        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(ValueError, match="must not be empty"):
                await client.crm_deal_update(deal_id=410, fields={})

    @pytest.mark.asyncio
    async def test_crm_deal_update_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_update should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.deal.update").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Update denied"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Update denied"):
                await client.crm_deal_update(deal_id=410, fields={"TITLE": "Blocked"})


class TestCrmDealDelete:
    """Tests for crm_deal_delete method."""

    @pytest.mark.asyncio
    async def test_crm_deal_delete_success(
        self, mock_webhook_url, sample_crm_deal_delete_response, mock_bitrix_api
    ):
        """crm_deal_delete should return delete status."""
        mock_bitrix_api.post("crm.deal.delete").mock(
            return_value=Response(200, json=sample_crm_deal_delete_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            deleted = await client.crm_deal_delete(deal_id=410)

        assert deleted is True

    @pytest.mark.asyncio
    async def test_crm_deal_delete_sends_id_payload(
        self, mock_webhook_url, sample_crm_deal_delete_response, mock_bitrix_api
    ):
        """crm_deal_delete should send id payload."""
        mock_bitrix_api.post("crm.deal.delete").mock(
            return_value=Response(200, json=sample_crm_deal_delete_response)
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            await client.crm_deal_delete(deal_id=410)

        import json

        request = mock_bitrix_api.calls[0].request
        body = json.loads(request.content)
        assert body["id"] == 410

    @pytest.mark.asyncio
    async def test_crm_deal_delete_requires_valid_id(self, mock_webhook_url):
        """crm_deal_delete should reject non-positive deal IDs."""
        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(ValueError, match="greater than 0"):
                await client.crm_deal_delete(deal_id=0)

    @pytest.mark.asyncio
    async def test_crm_deal_delete_api_error(self, mock_webhook_url, mock_bitrix_api):
        """crm_deal_delete should raise BitrixAPIError on API errors."""
        mock_bitrix_api.post("crm.deal.delete").mock(
            return_value=Response(
                200,
                json={"error": "ERROR_CORE", "error_description": "Deal not found"},
            )
        )

        async with Bitrix24Client(webhook_url=mock_webhook_url) as client:
            with pytest.raises(BitrixAPIError, match="Deal not found"):
                await client.crm_deal_delete(deal_id=99999)


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
