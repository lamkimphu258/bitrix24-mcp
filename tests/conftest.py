"""Pytest configuration and fixtures for Bitrix24 MCP tests."""

import pytest
import respx


@pytest.fixture
def mock_webhook_url() -> str:
    """Return a mock webhook URL for testing."""
    return "https://test.bitrix24.com/rest/1/test-token/"


@pytest.fixture(autouse=True)
def _force_mock_webhook_env(monkeypatch: pytest.MonkeyPatch, mock_webhook_url: str) -> None:
    """Force tests to use a safe, mock webhook URL.

    This prevents accidentally running tests against a real Bitrix24 inbound webhook
    if the developer has BITRIX_WEBHOOK_URL set in their environment.
    """
    monkeypatch.setenv("BITRIX_WEBHOOK_URL", mock_webhook_url)


@pytest.fixture
def sample_task_list_response() -> dict:
    """Return sample response for tasks.task.list API."""
    return {
        "result": {
            "tasks": [
                {
                    "id": "456",
                    "title": "Auto Send welcome email",
                    "responsibleId": "7",
                    "groupId": "5",
                    "status": "2",
                },
                {
                    "id": "789",
                    "title": "Welcome email template",
                    "responsibleId": "7",
                    "groupId": "5",
                    "status": "3",
                },
            ]
        }
    }


@pytest.fixture
def sample_task_get_response() -> dict:
    """Return sample response for tasks.task.get API."""
    return {
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
                "ufTaskWebdavFiles": [1065, 1077],
            }
        }
    }


@pytest.fixture
def sample_crm_deal_get_response() -> dict:
    """Return sample response for crm.deal.get API."""
    return {
        "result": {
            "ID": "410",
            "TITLE": "New Deal #1",
            "TYPE_ID": "COMPLEX",
            "CATEGORY_ID": "0",
            "STAGE_ID": "PREPARATION",
            "STAGE_SEMANTIC_ID": "P",
            "IS_NEW": "N",
            "IS_RECURRING": "N",
            "IS_RETURN_CUSTOMER": "N",
            "IS_REPEATED_APPROACH": "N",
            "PROBABILITY": "99",
            "CURRENCY_ID": "EUR",
            "OPPORTUNITY": "1000000.00",
            "IS_MANUAL_OPPORTUNITY": "Y",
            "TAX_VALUE": "0.00",
            "COMPANY_ID": "9",
            "CONTACT_ID": "84",
            "QUOTE_ID": None,
            "LEAD_ID": None,
            "BEGINDATE": "2024-08-30T02:00:00+02:00",
            "CLOSEDATE": "2024-09-09T02:00:00+02:00",
            "OPENED": "Y",
            "CLOSED": "N",
            "COMMENTS": "[B]Example comment[/B]",
            "ASSIGNED_BY_ID": "1",
            "CREATED_BY_ID": "1",
            "MODIFY_BY_ID": "1",
            "MOVED_BY_ID": "1",
            "DATE_CREATE": "2024-08-30T14:29:00+02:00",
            "DATE_MODIFY": "2024-08-30T14:29:00+02:00",
            "MOVED_TIME": "2024-08-30T14:29:00+02:00",
            "SOURCE_ID": "CALLBACK",
            "SOURCE_DESCRIPTION": "Additional information about the source",
            "ADDITIONAL_INFO": "Additional information",
            "LOCATION_ID": None,
            "ORIGINATOR_ID": None,
            "ORIGIN_ID": None,
            "UTM_SOURCE": "google",
            "UTM_MEDIUM": "CPC",
            "UTM_CAMPAIGN": None,
            "UTM_CONTENT": None,
            "UTM_TERM": None,
            "LAST_ACTIVITY_TIME": "2024-08-30T14:29:00+02:00",
            "LAST_ACTIVITY_BY": "1",
            "UF_CRM_1721244482250": "Hello world!",
            "PARENT_ID_153": "22",
        }
    }


@pytest.fixture
def sample_crm_deal_list_response() -> dict:
    """Return sample response for crm.deal.list API."""
    return {
        "result": [
            {
                "ID": "410",
                "TITLE": "New Deal #1",
                "TYPE_ID": "COMPLEX",
                "CATEGORY_ID": "0",
                "STAGE_ID": "PREPARATION",
                "OPPORTUNITY": "1000000.00",
                "ASSIGNED_BY_ID": "1",
                "CONTACT_ID": "84",
                "DATE_CREATE": "2024-08-30T14:29:00+02:00",
                "UF_CRM_1721244482250": "Hello world!",
            },
            {
                "ID": "411",
                "TITLE": "New Deal #2",
                "TYPE_ID": "SALE",
                "CATEGORY_ID": "1",
                "STAGE_ID": "C1:NEW",
                "OPPORTUNITY": "25000.00",
                "ASSIGNED_BY_ID": "6",
                "CONTACT_ID": "85",
                "DATE_CREATE": "2024-09-01T10:00:00+02:00",
            },
        ],
        "total": 120,
        "next": 50,
    }


@pytest.fixture
def sample_crm_deal_fields_response() -> dict:
    """Return sample response for crm.deal.fields API."""
    return {
        "result": {
            "ID": {
                "type": "integer",
                "isRequired": False,
                "isReadOnly": True,
                "isImmutable": False,
                "isMultiple": False,
                "isDynamic": False,
                "title": "ID",
            },
            "TITLE": {
                "type": "string",
                "isRequired": True,
                "isReadOnly": False,
                "isImmutable": False,
                "isMultiple": False,
                "isDynamic": False,
                "title": "Title",
            },
            "CONTACT_ID": {
                "type": "crm_contact",
                "isRequired": False,
                "isReadOnly": False,
                "isImmutable": False,
                "isMultiple": False,
                "isDynamic": False,
                "title": "Contact",
            },
            "ASSIGNED_BY_ID": {
                "type": "user",
                "isRequired": False,
                "isReadOnly": False,
                "isImmutable": False,
                "isMultiple": False,
                "isDynamic": False,
                "title": "Responsible",
            },
        }
    }


@pytest.fixture
def sample_crm_deal_productrows_get_response() -> dict:
    """Return sample response for crm.deal.productrows.get API."""
    return {
        "result": [
            {
                "ID": "120",
                "PRODUCT_ID": "101",
                "PRODUCT_NAME": "Website Subscription",
                "PRICE": "99.00",
                "QUANTITY": "1",
                "DISCOUNT_SUM": "0.00",
                "TAX_RATE": "0.00",
                "CURRENCY": "USD",
            },
            {
                "ID": "121",
                "PRODUCT_ID": "102",
                "PRODUCT_NAME": "Onboarding Package",
                "PRICE": "250.00",
                "QUANTITY": "1",
                "DISCOUNT_SUM": "25.00",
                "TAX_RATE": "0.00",
                "CURRENCY": "USD",
            },
        ]
    }


@pytest.fixture
def sample_crm_deal_add_response() -> dict:
    """Return sample response for crm.deal.add API."""
    return {"result": 512}


@pytest.fixture
def sample_task_comment_list_response() -> dict:
    """Return sample response for task.commentitem.getlist API."""
    return {
        "result": [
            {
                "POST_MESSAGE_HTML": None,
                "ID": "3155",
                "AUTHOR_ID": "503",
                "AUTHOR_NAME": "John Smith",
                "AUTHOR_EMAIL": "",
                "POST_DATE": "2025-07-15T14:30:00+02:00",
                "POST_MESSAGE": "Prepared new photos",
                "ATTACHED_OBJECTS": {},
            },
            {
                "POST_MESSAGE_HTML": None,
                "ID": "3157",
                "AUTHOR_ID": "503",
                "AUTHOR_NAME": "John Smith",
                "AUTHOR_EMAIL": "",
                "POST_DATE": "2025-07-15T14:31:00+02:00",
                "POST_MESSAGE": "Photos attached",
                "ATTACHED_OBJECTS": {
                    "973": {
                        "ATTACHMENT_ID": "973",
                        "NAME": "photo1.png",
                        "SIZE": "1495700",
                        "FILE_ID": "4755",
                        "DOWNLOAD_URL": "/download",
                        "VIEW_URL": "/view",
                    }
                },
            },
        ]
    }


@pytest.fixture
def sample_task_comment_add_response() -> dict:
    """Return sample response for task.commentitem.add API."""
    return {"result": "3158"}


@pytest.fixture
def sample_task_add_response() -> dict:
    """Return sample response for tasks.task.add API."""
    return {
        "result": {
            "task": {
                "id": 457,
            }
        }
    }


@pytest.fixture
def sample_scrum_sprint_list_response() -> dict:
    """Return sample response for tasks.api.scrum.sprint.list API."""
    return {
        "result": [
            {
                "id": 5,
                "groupId": 5,
                "entityType": "sprint",
                "name": "Sprint 5",
                "goal": "",
                "sort": 1,
                "createdBy": 1,
                "modifiedBy": 1,
                "dateStart": "2025-12-01T00:00:00+00:00",
                "dateEnd": "2025-12-31T23:59:59+00:00",
                "status": "active",
            },
            {
                "id": 4,
                "groupId": 5,
                "entityType": "sprint",
                "name": "Sprint 4",
                "goal": "",
                "sort": 1,
                "createdBy": 1,
                "modifiedBy": 1,
                "dateStart": "2025-11-01T00:00:00+00:00",
                "dateEnd": "2025-11-30T23:59:59+00:00",
                "status": "completed",
            },
        ]
    }


@pytest.fixture
def sample_scrum_kanban_get_stages_response() -> dict:
    """Return sample response for tasks.api.scrum.kanban.getStages API."""
    return {
        "result": [
            {
                "id": "58",
                "name": "To Do",
                "sort": "100",
                "type": "NEW",
                "sprintId": "5",
                "color": "00C4FB",
            },
            {
                "id": "59",
                "name": "In Progress",
                "sort": "200",
                "type": "WORK",
                "sprintId": "5",
                "color": "47D1E2",
            },
            {
                "id": "60",
                "name": "Done",
                "sort": "300",
                "type": "FINISH",
                "sprintId": "5",
                "color": "75D900",
            },
        ]
    }


@pytest.fixture
def sample_scrum_epic_list_response() -> dict:
    """Return sample response for tasks.api.scrum.epic.list API."""
    return {
        "result": [
            {
                "id": 1,
                "groupId": 5,
                "name": "Dashboard",
                "description": "",
                "createdBy": 1,
                "modifiedBy": 1,
                "color": "#69dafc",
            },
            {
                "id": 2,
                "groupId": 5,
                "name": "CMS",
                "description": "Content management work",
                "createdBy": 1,
                "modifiedBy": 1,
                "color": "#75D900",
            },
        ]
    }


@pytest.fixture
def sample_scrum_task_get_response() -> dict:
    """Return sample response for tasks.api.scrum.task.get API."""
    return {
        "result": {
            "entityId": 2,
            "storyPoints": "2",
            "epicId": 1,
            "sort": 1,
            "createdBy": 1,
            "modifiedBy": 1,
        }
    }


@pytest.fixture
def sample_scrum_task_update_response() -> dict:
    """Return sample response for tasks.api.scrum.task.update API."""
    return {"result": {"status": "success", "data": True, "errors": []}}


@pytest.fixture
def sample_task_data() -> dict:
    """Return sample task data for creating tasks."""
    return {
        "title": "Set up email service configuration",
        "description": "Configure SMTP server or email service (SendGrid/AWS SES).",
        "responsibleId": 7,
        "groupId": 5,
        "parentId": 456,
        "priority": 1,
    }


@pytest.fixture(autouse=True)
def mock_bitrix_api(mock_webhook_url):
    """Create a respx mock for Bitrix24 API.

    This fixture is autouse to ensure NO tests can make real network requests.
    Any HTTPX request not explicitly mocked will fail fast.
    """
    with respx.mock(base_url=mock_webhook_url, assert_all_mocked=True) as respx_mock:
        yield respx_mock


@pytest.fixture
def api_error_response() -> dict:
    """Return sample API error response."""
    return {
        "error": "TASK_NOT_FOUND",
        "error_description": "Task not found",
    }


@pytest.fixture
def sample_user_get_response() -> dict:
    """Return sample response for user.get API."""
    return {
        "result": [
            {
                "ID": "7",
                "NAME": "John",
                "LAST_NAME": "Doe",
                "EMAIL": "john@company.com",
                "ACTIVE": True,
            },
            {
                "ID": "8",
                "NAME": "Johnny",
                "LAST_NAME": "Smith",
                "EMAIL": "johnny@company.com",
                "ACTIVE": True,
            },
        ]
    }


@pytest.fixture
def sample_single_user_response() -> dict:
    """Return sample response for user.get API with single user."""
    return {
        "result": [
            {
                "ID": "7",
                "NAME": "John",
                "LAST_NAME": "Doe",
                "EMAIL": "john@company.com",
                "ACTIVE": True,
            },
        ]
    }


@pytest.fixture
def sample_user_list_page1() -> dict:
    """Return first page of users for pagination testing (50 users)."""
    users = [
        {
            "ID": str(i),
            "NAME": f"User{i}",
            "LAST_NAME": f"Last{i}",
            "EMAIL": f"user{i}@company.com",
            "ACTIVE": True,
        }
        for i in range(1, 51)  # Users 1-50
    ]
    return {"result": users}


@pytest.fixture
def sample_user_list_page2() -> dict:
    """Return second page of users for pagination testing (25 users - last page)."""
    users = [
        {
            "ID": str(i),
            "NAME": f"User{i}",
            "LAST_NAME": f"Last{i}",
            "EMAIL": f"user{i}@company.com",
            "ACTIVE": True,
        }
        for i in range(51, 76)  # Users 51-75
    ]
    # Add a user named "Phu" to test filtering
    users.append(
        {
            "ID": "100",
            "NAME": "Phu",
            "LAST_NAME": "Nguyen",
            "EMAIL": "phu@company.com",
            "ACTIVE": True,
        }
    )
    return {"result": users}


@pytest.fixture
def sample_group_search_response() -> dict:
    """Return sample response for searching groups via sonet_group.get."""
    return {
        "result": [
            {
                "ID": "205",
                "NAME": "MusicFlowx Development",
                "DESCRIPTION": "Development tasks for MusicFlowx platform",
                "OWNER_ID": "22",
                "PROJECT": "Y",
                "SCRUM_MASTER_ID": "1665",
            },
            {
                "ID": "206",
                "NAME": "MusicFlowx QA",
                "DESCRIPTION": "QA tasks for MusicFlowx platform",
                "OWNER_ID": "23",
                "PROJECT": "Y",
                "SCRUM_MASTER_ID": "1665",
            },
        ]
    }
