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


class BitrixDeal(BaseModel):
    """Represents a Bitrix24 CRM deal (crm.deal.get)."""

    id: str = Field(alias="ID")
    title: str = Field(alias="TITLE")
    type_id: str | None = Field(default=None, alias="TYPE_ID")
    category_id: str | None = Field(default=None, alias="CATEGORY_ID")
    stage_id: str | None = Field(default=None, alias="STAGE_ID")
    stage_semantic_id: str | None = Field(default=None, alias="STAGE_SEMANTIC_ID")
    is_new: str | None = Field(default=None, alias="IS_NEW")
    is_recurring: str | None = Field(default=None, alias="IS_RECURRING")
    is_return_customer: str | None = Field(default=None, alias="IS_RETURN_CUSTOMER")
    is_repeated_approach: str | None = Field(default=None, alias="IS_REPEATED_APPROACH")
    probability: str | None = Field(default=None, alias="PROBABILITY")
    currency_id: str | None = Field(default=None, alias="CURRENCY_ID")
    opportunity: str | None = Field(default=None, alias="OPPORTUNITY")
    is_manual_opportunity: str | None = Field(default=None, alias="IS_MANUAL_OPPORTUNITY")
    tax_value: str | None = Field(default=None, alias="TAX_VALUE")
    company_id: str | None = Field(default=None, alias="COMPANY_ID")
    contact_id: str | None = Field(default=None, alias="CONTACT_ID")
    quote_id: str | None = Field(default=None, alias="QUOTE_ID")
    lead_id: str | None = Field(default=None, alias="LEAD_ID")
    begin_date: str | None = Field(default=None, alias="BEGINDATE")
    close_date: str | None = Field(default=None, alias="CLOSEDATE")
    opened: str | None = Field(default=None, alias="OPENED")
    closed: str | None = Field(default=None, alias="CLOSED")
    comments: str | None = Field(default=None, alias="COMMENTS")
    assigned_by_id: str | None = Field(default=None, alias="ASSIGNED_BY_ID")
    created_by_id: str | None = Field(default=None, alias="CREATED_BY_ID")
    modify_by_id: str | None = Field(default=None, alias="MODIFY_BY_ID")
    moved_by_id: str | None = Field(default=None, alias="MOVED_BY_ID")
    date_create: str | None = Field(default=None, alias="DATE_CREATE")
    date_modify: str | None = Field(default=None, alias="DATE_MODIFY")
    moved_time: str | None = Field(default=None, alias="MOVED_TIME")
    source_id: str | None = Field(default=None, alias="SOURCE_ID")
    source_description: str | None = Field(default=None, alias="SOURCE_DESCRIPTION")
    additional_info: str | None = Field(default=None, alias="ADDITIONAL_INFO")
    location_id: str | None = Field(default=None, alias="LOCATION_ID")
    originator_id: str | None = Field(default=None, alias="ORIGINATOR_ID")
    origin_id: str | None = Field(default=None, alias="ORIGIN_ID")
    utm_source: str | None = Field(default=None, alias="UTM_SOURCE")
    utm_medium: str | None = Field(default=None, alias="UTM_MEDIUM")
    utm_campaign: str | None = Field(default=None, alias="UTM_CAMPAIGN")
    utm_content: str | None = Field(default=None, alias="UTM_CONTENT")
    utm_term: str | None = Field(default=None, alias="UTM_TERM")
    last_activity_time: str | None = Field(default=None, alias="LAST_ACTIVITY_TIME")
    last_activity_by: str | None = Field(default=None, alias="LAST_ACTIVITY_BY")

    model_config = {"populate_by_name": True, "extra": "allow"}

    @staticmethod
    def _to_int(value: Any) -> int | None:  # noqa: ANN401
        """Convert numeric-like values to int when possible."""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_flag(value: Any) -> bool | None:  # noqa: ANN401
        """Convert Bitrix24 Y/N flags to booleans."""
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        if normalized == "Y":
            return True
        if normalized == "N":
            return False
        return None

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        extras = self.model_extra or {}

        user_fields: dict[str, Any] = {}
        parent_ids: dict[str, Any] = {}
        extra_fields: dict[str, Any] = {}

        for key, value in extras.items():
            if key.startswith("UF_CRM_"):
                user_fields[key] = value
                continue
            if key.startswith("PARENT_ID_"):
                parent_id = self._to_int(value)
                parent_ids[key] = parent_id if parent_id is not None else value
                continue
            extra_fields[key] = value

        result = {
            "id": int(self.id),
            "title": self.title,
            "typeId": self.type_id,
            "categoryId": self._to_int(self.category_id),
            "stageId": self.stage_id,
            "stageSemanticId": self.stage_semantic_id,
            "isNew": self._to_flag(self.is_new),
            "isRecurring": self._to_flag(self.is_recurring),
            "isReturnCustomer": self._to_flag(self.is_return_customer),
            "isRepeatedApproach": self._to_flag(self.is_repeated_approach),
            "probability": self._to_int(self.probability),
            "currencyId": self.currency_id,
            "opportunity": self.opportunity,
            "isManualOpportunity": self._to_flag(self.is_manual_opportunity),
            "taxValue": self.tax_value,
            "companyId": self._to_int(self.company_id),
            "contactId": self._to_int(self.contact_id),
            "quoteId": self._to_int(self.quote_id),
            "leadId": self._to_int(self.lead_id),
            "beginDate": self.begin_date,
            "closeDate": self.close_date,
            "opened": self._to_flag(self.opened),
            "closed": self._to_flag(self.closed),
            "comments": self.comments,
            "assignedById": self._to_int(self.assigned_by_id),
            "createdById": self._to_int(self.created_by_id),
            "modifyById": self._to_int(self.modify_by_id),
            "movedById": self._to_int(self.moved_by_id),
            "dateCreate": self.date_create,
            "dateModify": self.date_modify,
            "movedTime": self.moved_time,
            "sourceId": self.source_id,
            "sourceDescription": self.source_description,
            "additionalInfo": self.additional_info,
            "locationId": self._to_int(self.location_id),
            "originatorId": self.originator_id,
            "originId": self.origin_id,
            "utmSource": self.utm_source,
            "utmMedium": self.utm_medium,
            "utmCampaign": self.utm_campaign,
            "utmContent": self.utm_content,
            "utmTerm": self.utm_term,
            "lastActivityTime": self.last_activity_time,
            "lastActivityBy": self._to_int(self.last_activity_by),
            "userFields": user_fields,
            "parentIds": parent_ids,
        }
        if extra_fields:
            result["extraFields"] = extra_fields
        return result


class BitrixLead(BaseModel):
    """Represents a Bitrix24 CRM lead (crm.lead.get)."""

    id: str = Field(alias="ID")
    title: str = Field(alias="TITLE")
    status_id: str | None = Field(default=None, alias="STATUS_ID")
    opened: str | None = Field(default=None, alias="OPENED")
    assigned_by_id: str | None = Field(default=None, alias="ASSIGNED_BY_ID")
    company_id: str | None = Field(default=None, alias="COMPANY_ID")
    contact_id: str | None = Field(default=None, alias="CONTACT_ID")
    source_id: str | None = Field(default=None, alias="SOURCE_ID")
    source_description: str | None = Field(default=None, alias="SOURCE_DESCRIPTION")
    comments: str | None = Field(default=None, alias="COMMENTS")
    opportunity: str | None = Field(default=None, alias="OPPORTUNITY")
    currency_id: str | None = Field(default=None, alias="CURRENCY_ID")
    address: str | None = Field(default=None, alias="ADDRESS")
    address_city: str | None = Field(default=None, alias="ADDRESS_CITY")
    address_region: str | None = Field(default=None, alias="ADDRESS_REGION")
    address_province: str | None = Field(default=None, alias="ADDRESS_PROVINCE")
    address_country: str | None = Field(default=None, alias="ADDRESS_COUNTRY")
    address_postal_code: str | None = Field(default=None, alias="ADDRESS_POSTAL_CODE")
    date_create: str | None = Field(default=None, alias="DATE_CREATE")
    date_modify: str | None = Field(default=None, alias="DATE_MODIFY")
    created_by_id: str | None = Field(default=None, alias="CREATED_BY_ID")
    modify_by_id: str | None = Field(default=None, alias="MODIFY_BY_ID")
    moved_by_id: str | None = Field(default=None, alias="MOVED_BY_ID")
    moved_time: str | None = Field(default=None, alias="MOVED_TIME")

    model_config = {"populate_by_name": True, "extra": "allow"}

    @staticmethod
    def _to_int(value: Any) -> int | None:  # noqa: ANN401
        """Convert numeric-like values to int when possible."""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_flag(value: Any) -> bool | None:  # noqa: ANN401
        """Convert Bitrix24 Y/N flags to booleans."""
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        if normalized == "Y":
            return True
        if normalized == "N":
            return False
        return None

    def to_result(self) -> dict[str, Any]:
        """Convert to result format for MCP tool response."""
        extras = self.model_extra or {}
        user_fields: dict[str, Any] = {}
        extra_fields: dict[str, Any] = {}

        for key, value in extras.items():
            if key.startswith("UF_CRM_"):
                user_fields[key] = value
                continue
            extra_fields[key] = value

        result = {
            "id": int(self.id),
            "title": self.title,
            "statusId": self.status_id,
            "opened": self._to_flag(self.opened),
            "assignedById": self._to_int(self.assigned_by_id),
            "companyId": self._to_int(self.company_id),
            "contactId": self._to_int(self.contact_id),
            "sourceId": self.source_id,
            "sourceDescription": self.source_description,
            "comments": self.comments,
            "opportunity": self.opportunity,
            "currencyId": self.currency_id,
            "address": self.address,
            "addressCity": self.address_city,
            "addressRegion": self.address_region,
            "addressProvince": self.address_province,
            "addressCountry": self.address_country,
            "addressPostalCode": self.address_postal_code,
            "dateCreate": self.date_create,
            "dateModify": self.date_modify,
            "createdById": self._to_int(self.created_by_id),
            "modifyById": self._to_int(self.modify_by_id),
            "movedById": self._to_int(self.moved_by_id),
            "movedTime": self.moved_time,
            "userFields": user_fields,
        }
        if extra_fields:
            result["extraFields"] = extra_fields
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
