"""Bitrix24 type definitions using Pydantic models."""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskStatus(IntEnum):
    """Bitrix24 task status codes."""

    PENDING = 2
    IN_PROGRESS = 3
    SUPPOSEDLY_COMPLETED = 4
    COMPLETED = 5
    DEFERRED = 6

    @classmethod
    def to_string(cls, status: int) -> str:
        """Convert status ID to human-readable string."""
        mapping = {
            2: "pending",
            3: "in_progress",
            4: "supposedly_completed",
            5: "completed",
            6: "deferred",
        }
        return mapping.get(status, "unknown")


class TaskPriority(IntEnum):
    """Bitrix24 task priority levels."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @classmethod
    def to_string(cls, priority: int) -> str:
        """Convert priority ID to human-readable string."""
        mapping = {
            0: "low",
            1: "medium",
            2: "high",
        }
        return mapping.get(priority, "medium")


class BitrixTask(BaseModel):
    """Represents a Bitrix24 task.

    The Bitrix24 API returns fields in camelCase format (e.g., responsibleId, groupId).
    """

    id: str
    title: str
    description: str | None = None
    responsible_id: str | None = Field(default=None, alias="responsibleId")
    group_id: str | None = Field(default=None, alias="groupId")
    stage_id: str | None = Field(default=None, alias="stageId")
    parent_id: str | None = Field(default=None, alias="parentId")
    status: str
    priority: str | None = None
    deadline: str | None = None
    created_by: str | None = Field(default=None, alias="createdBy")
    attachment_file_ids: list[int] | None = Field(default=None, alias="ufTaskWebdavFiles")

    model_config = {"populate_by_name": True}

    @field_validator("attachment_file_ids", mode="before")
    @classmethod
    def _normalize_attachment_file_ids(cls, v: Any) -> Any:  # noqa: ANN401
        """Normalize UF_TASK_WEBDAV_FILES.

        Bitrix24 sometimes returns `false` for ufTaskWebdavFiles when there are no attachments.
        We normalize that to an empty list so Pydantic validation and tool output are stable.
        """
        if v is False or v is None:
            return []
        return v

    def get_url(self, base_url: str) -> str | None:
        """Generate Bitrix24 task URL.

        Args:
            base_url: Base URL (e.g., https://example.bitrix24.com)

        Returns:
            Task URL or None if group_id is not set
        """
        if not self.group_id:
            return None
        return f"{base_url}/workgroups/group/{self.group_id}/tasks/task/view/{self.id}/"

    def to_search_result(self, base_url: str | None = None) -> dict[str, Any]:
        """Convert to search result format for MCP tool response.

        Args:
            base_url: Optional base URL for generating task URL
        """
        result = {
            "id": int(self.id),
            "title": self.title,
            "responsibleId": int(self.responsible_id) if self.responsible_id else None,
            "groupId": int(self.group_id) if self.group_id else None,
            "parentId": int(self.parent_id) if self.parent_id else None,
            "status": TaskStatus.to_string(int(self.status)),
        }
        if base_url:
            result["url"] = self.get_url(base_url)
        return result

    def to_detail_result(self, base_url: str | None = None) -> dict[str, Any]:
        """Convert to detailed result format for MCP tool response.

        Args:
            base_url: Optional base URL for generating task URL
        """
        result = {
            "id": int(self.id),
            "title": self.title,
            "description": self.description,
            "responsibleId": int(self.responsible_id) if self.responsible_id else None,
            "groupId": int(self.group_id) if self.group_id else None,
            "stageId": int(self.stage_id) if self.stage_id else None,
            "parentId": int(self.parent_id) if self.parent_id else None,
            "status": TaskStatus.to_string(int(self.status)),
            "priority": TaskPriority.to_string(int(self.priority)) if self.priority else "medium",
            "deadline": self.deadline,
            "createdBy": int(self.created_by) if self.created_by else None,
            "attachmentFileIds": self.attachment_file_ids or [],
        }
        if base_url:
            result["url"] = self.get_url(base_url)
        return result


class BitrixTaskStage(BaseModel):
    """Represents a Bitrix24 Kanban/"My Planner" stage (task.stages.get)."""

    id: str = Field(alias="ID")
    title: str = Field(alias="TITLE")
    sort: str | None = Field(default=None, alias="SORT")
    color: str | None = Field(default=None, alias="COLOR")
    system_type: str | None = Field(default=None, alias="SYSTEM_TYPE")
    entity_id: str | None = Field(default=None, alias="ENTITY_ID")
    entity_type: str | None = Field(default=None, alias="ENTITY_TYPE")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        return {
            "id": int(self.id),
            "title": self.title,
            "sort": int(self.sort) if self.sort else None,
            "color": self.color,
            "systemType": self.system_type,
            "entityId": int(self.entity_id) if self.entity_id else None,
            "entityType": self.entity_type,
        }


class BitrixScrumSprint(BaseModel):
    """Represents a Bitrix24 Scrum sprint (tasks.api.scrum.sprint.list)."""

    id: int
    group_id: int | None = Field(default=None, alias="groupId")
    entity_type: str | None = Field(default=None, alias="entityType")
    name: str | None = None
    date_start: str | None = Field(default=None, alias="dateStart")
    date_end: str | None = Field(default=None, alias="dateEnd")
    status: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}


class BitrixScrumKanbanStage(BaseModel):
    """Represents a Bitrix24 Scrum Kanban stage (tasks.api.scrum.kanban.getStages)."""

    id: str
    name: str
    sort: str | None = None
    type: str | None = None
    sprint_id: str | None = Field(default=None, alias="sprintId")
    color: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        return {
            "id": int(self.id),
            "title": self.name,
            "sort": int(self.sort) if self.sort else None,
            "color": self.color,
            "systemType": self.type,
            "sprintId": int(self.sprint_id) if self.sprint_id else None,
        }


class BitrixScrumEpic(BaseModel):
    """Represents a Bitrix24 Scrum epic (tasks.api.scrum.epic.*)."""

    id: int
    group_id: int | None = Field(default=None, alias="groupId")
    name: str
    description: str | None = None
    created_by: int | None = Field(default=None, alias="createdBy")
    modified_by: int | None = Field(default=None, alias="modifiedBy")
    color: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        return {
            "id": self.id,
            "groupId": self.group_id,
            "name": self.name,
            "description": self.description,
            "createdBy": self.created_by,
            "modifiedBy": self.modified_by,
            "color": self.color,
        }


class BitrixScrumTask(BaseModel):
    """Represents Scrum-specific fields for a task (tasks.api.scrum.task.get)."""

    entity_id: int | None = Field(default=None, alias="entityId")
    story_points: str | None = Field(default=None, alias="storyPoints")
    epic_id: int | None = Field(default=None, alias="epicId")
    sort: int | None = None
    created_by: int | None = Field(default=None, alias="createdBy")
    modified_by: int | None = Field(default=None, alias="modifiedBy")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        return {
            "entityId": self.entity_id,
            "storyPoints": self.story_points,
            "epicId": self.epic_id,
            "sort": self.sort,
            "createdBy": self.created_by,
            "modifiedBy": self.modified_by,
        }


class BitrixTaskCommentAttachment(BaseModel):
    """Represents a file attachment on a task comment."""

    attachment_id: str = Field(alias="ATTACHMENT_ID")
    name: str = Field(alias="NAME")
    size: str | None = Field(default=None, alias="SIZE")
    file_id: str | None = Field(default=None, alias="FILE_ID")

    # These fields may include auth tokens; we intentionally do not expose them in tool output.
    download_url: str | None = Field(default=None, alias="DOWNLOAD_URL")
    view_url: str | None = Field(default=None, alias="VIEW_URL")

    model_config = {"populate_by_name": True}

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response (sanitized)."""
        return {
            "attachmentId": int(self.attachment_id),
            "name": self.name,
            "size": int(self.size) if self.size else None,
            "fileId": int(self.file_id) if self.file_id else None,
        }


class BitrixTaskComment(BaseModel):
    """Represents a Bitrix24 task comment (task.commentitem.*).

    Bitrix24 returns comment fields in UPPERCASE format (e.g., POST_MESSAGE, AUTHOR_ID).
    """

    id: str = Field(alias="ID")
    author_id: str | None = Field(default=None, alias="AUTHOR_ID")
    author_name: str | None = Field(default=None, alias="AUTHOR_NAME")
    author_email: str | None = Field(default=None, alias="AUTHOR_EMAIL")
    post_date: str | None = Field(default=None, alias="POST_DATE")
    post_message: str | None = Field(default=None, alias="POST_MESSAGE")
    post_message_html: str | None = Field(default=None, alias="POST_MESSAGE_HTML")
    attached_objects: dict[str, BitrixTaskCommentAttachment] = Field(
        default_factory=dict, alias="ATTACHED_OBJECTS"
    )

    model_config = {"populate_by_name": True}

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        return {
            "id": int(self.id),
            "authorId": int(self.author_id) if self.author_id else None,
            "authorName": self.author_name,
            "authorEmail": self.author_email or None,
            "postDate": self.post_date,
            "message": self.post_message,
            "messageHtml": self.post_message_html,
            "attachments": [a.to_result() for a in self.attached_objects.values()],
        }


class BitrixUser(BaseModel):
    """Represents a Bitrix24 user.

    The Bitrix24 user API returns fields in UPPERCASE format (e.g., ID, NAME, LAST_NAME).
    """

    id: str = Field(alias="ID")
    name: str = Field(alias="NAME")
    last_name: str = Field(default="", alias="LAST_NAME")
    email: str | None = Field(default=None, alias="EMAIL")
    active: bool = Field(default=True, alias="ACTIVE")

    model_config = {"populate_by_name": True}

    def to_search_result(self) -> dict[str, Any]:
        """Convert to search result format for MCP tool response."""
        full_name = f"{self.name} {self.last_name}".strip()
        return {
            "id": int(self.id),
            "name": full_name,
            "email": self.email,
        }


class BitrixGroup(BaseModel):
    """Represents a Bitrix24 workgroup/scrum.

    The Bitrix24 sonet_group API returns fields in UPPERCASE format.
    """

    id: str = Field(alias="ID")
    name: str = Field(alias="NAME")
    description: str | None = Field(default=None, alias="DESCRIPTION")
    owner_id: str | None = Field(default=None, alias="OWNER_ID")
    project: str | None = Field(default=None, alias="PROJECT")
    scrum_master_id: str | None = Field(default=None, alias="SCRUM_MASTER_ID")

    model_config = {"populate_by_name": True}

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        return {
            "id": int(self.id),
            "name": self.name,
            "description": self.description,
            "ownerId": int(self.owner_id) if self.owner_id else None,
            "isProject": self.project == "Y" if self.project else False,
            "scrumMasterId": int(self.scrum_master_id) if self.scrum_master_id else None,
        }


class BitrixAPIError(Exception):
    """Exception raised for Bitrix24 API errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        error_description: str | None = None,
    ):
        self.error_code = error_code
        self.error_description = error_description
        super().__init__(message)


class BitrixConnectionError(Exception):
    """Exception raised for connection errors to Bitrix24."""

    pass
