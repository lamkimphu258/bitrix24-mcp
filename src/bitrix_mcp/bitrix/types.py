"""Bitrix24 type definitions using Pydantic models."""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


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
    parent_id: str | None = Field(default=None, alias="parentId")
    status: str
    priority: str | None = None
    deadline: str | None = None
    created_by: str | None = Field(default=None, alias="createdBy")

    model_config = {"populate_by_name": True}

    def to_search_result(self) -> dict[str, Any]:
        """Convert to search result format for MCP tool response."""
        return {
            "id": int(self.id),
            "title": self.title,
            "responsibleId": int(self.responsible_id) if self.responsible_id else None,
            "groupId": int(self.group_id) if self.group_id else None,
            "status": TaskStatus.to_string(int(self.status)),
        }

    def to_detail_result(self) -> dict[str, Any]:
        """Convert to detailed result format for MCP tool response."""
        return {
            "id": int(self.id),
            "title": self.title,
            "description": self.description,
            "responsibleId": int(self.responsible_id) if self.responsible_id else None,
            "groupId": int(self.group_id) if self.group_id else None,
            "parentId": int(self.parent_id) if self.parent_id else None,
            "status": TaskStatus.to_string(int(self.status)),
            "priority": TaskPriority.to_string(int(self.priority)) if self.priority else "medium",
            "deadline": self.deadline,
            "createdBy": int(self.created_by) if self.created_by else None,
        }


class BitrixAPIError(Exception):
    """Exception raised for Bitrix24 API errors."""

    def __init__(self, message: str, error_code: str | None = None, error_description: str | None = None):
        self.error_code = error_code
        self.error_description = error_description
        super().__init__(message)


class BitrixConnectionError(Exception):
    """Exception raised for connection errors to Bitrix24."""

    pass
