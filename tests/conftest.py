"""Pytest configuration and fixtures for Bitrix24 MCP tests."""

import pytest
import respx


@pytest.fixture
def mock_webhook_url() -> str:
    """Return a mock webhook URL for testing."""
    return "https://test.bitrix24.com/rest/1/test-token/"


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
                "createdBy": "1",
                "status": "2",
                "deadline": None,
                "parentId": None,
                "priority": "1",
            }
        }
    }


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


@pytest.fixture
def mock_bitrix_api(mock_webhook_url):
    """Create a respx mock for Bitrix24 API."""
    with respx.mock(base_url=mock_webhook_url) as respx_mock:
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
