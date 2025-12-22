"""Integration tests for Bitrix24 MCP Server.

These tests verify the complete workflow of searching for a task,
getting its details, and creating subtasks.
"""

import pytest
from httpx import Response

from bitrix_mcp.bitrix.client import Bitrix24Client
from bitrix_mcp.server import _task_create, _task_get, _task_search, set_client


@pytest.fixture
def setup_integration(mock_webhook_url, mock_bitrix_api):
    """Set up client for integration tests."""
    client = Bitrix24Client(webhook_url=mock_webhook_url)
    set_client(client)
    yield mock_bitrix_api


class TestWorkflowSearchAndGet:
    """Test the search → get workflow."""

    @pytest.mark.asyncio
    async def test_find_task_and_get_details(self, setup_integration):
        """User can search for a task and get its full details."""
        mock_api = setup_integration

        # Step 1: Search for task by name
        mock_api.post("tasks.task.list").mock(
            return_value=Response(
                200,
                json={
                    "result": {
                        "tasks": [
                            {
                                "id": "456",
                                "title": "Auto Send welcome email",
                                "responsibleId": "7",
                                "groupId": "5",
                                "status": "2",
                            }
                        ]
                    }
                },
            )
        )

        search_results = await _task_search(query="Auto Send welcome email")
        assert len(search_results) == 1
        task_id = search_results[0]["id"]
        assert task_id == 456

        # Step 2: Get full task details
        mock_api.post("tasks.task.get").mock(
            return_value=Response(
                200,
                json={
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
                },
            )
        )

        task_details = await _task_get(id=task_id)

        # Verify we have all needed info for subtask creation
        assert task_details["id"] == 456
        assert task_details["description"] == "Any new sign up user, send welcome email."
        assert task_details["responsibleId"] == 7
        assert task_details["groupId"] == 5


class TestWorkflowCreateSubtasks:
    """Test the get parent → create subtasks workflow."""

    @pytest.mark.asyncio
    async def test_create_multiple_subtasks(self, setup_integration):
        """User can create multiple subtasks under a parent task."""
        mock_api = setup_integration

        # Parent task info (from task_get)
        parent_id = 456
        parent_responsible_id = 7
        parent_group_id = 5

        # Subtasks to create (as AI would propose)
        subtasks = [
            {
                "title": "Set up email service configuration",
                "description": "Configure SMTP server or email service (SendGrid/AWS SES).",
            },
            {
                "title": "Create welcome email template",
                "description": (
                    "Design HTML template with welcome message, branding, and unsubscribe link."
                ),
            },
            {
                "title": "Implement user signup event listener",
                "description": "Set up event listener to trigger on new user registration.",
            },
        ]

        # Mock task creation responses
        created_ids = [457, 458, 459]
        for created_id in created_ids:
            mock_api.post("tasks.task.add").mock(
                return_value=Response(200, json={"result": {"task": {"id": created_id}}})
            )

        # Create subtasks
        results = []
        for subtask in subtasks:
            result = await _task_create(
                title=subtask["title"],
                description=subtask["description"],
                responsibleId=parent_responsible_id,
                groupId=parent_group_id,
                parentId=parent_id,
            )
            results.append(result)

        # Verify all subtasks created
        assert len(results) == 3
        assert all("id" in r for r in results)
        assert all("title" in r for r in results)

        # Verify correct API calls were made
        assert mock_api.calls.call_count == 3

        # Verify each call had parent task info
        import json

        for call in mock_api.calls:
            body = json.loads(call.request.content)
            fields = body["fields"]
            assert fields["RESPONSIBLE_ID"] == parent_responsible_id
            assert fields["GROUP_ID"] == parent_group_id
            assert fields["PARENT_ID"] == parent_id


class TestFullWorkflow:
    """Test the complete planning workflow."""

    @pytest.mark.asyncio
    async def test_complete_task_planning_workflow(self, setup_integration):
        """Test the full workflow: search → get → (AI analysis) → create subtasks."""
        mock_api = setup_integration

        # === STEP 1: User requests "Plan for task Auto Send welcome email" ===

        # Search for the task
        mock_api.post("tasks.task.list").mock(
            return_value=Response(
                200,
                json={
                    "result": {
                        "tasks": [
                            {
                                "id": "456",
                                "title": "Auto Send welcome email",
                                "responsibleId": "7",
                                "groupId": "5",
                                "status": "2",
                            }
                        ]
                    }
                },
            )
        )

        search_results = await _task_search(query="Auto Send welcome email")
        parent_task_id = search_results[0]["id"]

        # === STEP 2: Get task details for AI analysis ===

        mock_api.post("tasks.task.get").mock(
            return_value=Response(
                200,
                json={
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
                },
            )
        )

        parent_task = await _task_get(id=parent_task_id)

        # Store parent info for subtask creation
        parent_info = {
            "id": parent_task["id"],
            "responsibleId": parent_task["responsibleId"],
            "groupId": parent_task["groupId"],
        }

        # === STEP 3: AI analyzes description and proposes subtasks ===
        # (In real usage, this is done by the AI based on parent_task["description"])

        proposed_subtasks = [
            {"title": "Set up email service configuration", "description": "Configure SMTP..."},
            {"title": "Create welcome email template", "description": "Design HTML template..."},
            {"title": "Implement user signup event listener", "description": "Set up event..."},
            {"title": "Implement email sending logic", "description": "Create service..."},
        ]

        # === STEP 4: User approves, create subtasks ===

        # Use side_effect to return different responses for each call
        task_add_responses = [
            Response(200, json={"result": {"task": {"id": 457 + i}}})
            for i in range(len(proposed_subtasks))
        ]
        mock_api.post("tasks.task.add").mock(side_effect=task_add_responses)

        created_tasks = []
        for subtask in proposed_subtasks:
            result = await _task_create(
                title=subtask["title"],
                description=subtask["description"],
                responsibleId=parent_info["responsibleId"],
                groupId=parent_info["groupId"],
                parentId=parent_info["id"],
            )
            created_tasks.append(result)

        # === VERIFY: All subtasks created with correct parent relationship ===

        assert len(created_tasks) == 4
        assert created_tasks[0]["id"] == 457
        assert created_tasks[1]["id"] == 458
        assert created_tasks[2]["id"] == 459
        assert created_tasks[3]["id"] == 460

        # Verify workflow made expected number of API calls
        # 1 search + 1 get + 4 creates = 6 total
        assert mock_api.calls.call_count == 6
