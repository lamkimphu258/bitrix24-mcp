# Bitrix24 MCP

**A Model Context Protocol server for Bitrix24 task planning.**

[![PyPI version](https://img.shields.io/pypi/v/bitrix24-lkp-mcp.svg)](https://pypi.org/project/bitrix24-lkp-mcp/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Bitrix24 MCP equips AI assistants with tools to search users and workgroups, search/list tasks, fetch task details (optionally with comments), create/update tasks and subtasks, list epics and create/update Scrum tasks (epic/story points/backlog or sprint), and manage Kanban/My Planner columns (get stages, move/reorder tasks).

---

Install using pip:

```bash
pip install bitrix24-lkp-mcp
```

Set your webhook URL and configure your MCP client:

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "uvx",
      "args": ["bitrix24-lkp-mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

## Features

Bitrix24 MCP provides tools for AI-assisted task planning:

- Search tasks by title with partial matching.
- Get full task details including description for AI analysis.
- Create subtasks under parent tasks automatically.
- Built-in rate limiting (respects Bitrix24's 2 req/sec limit).
- Secure authentication via Bitrix24 inbound webhooks.


Bitrix24 MCP requires Python 3.11+.

## Configuration

### 1. Create Bitrix24 Webhook

1. Go to your Bitrix24 portal
2. Navigate to **Developer resources** → **Other** → **Inbound webhook**
3. Click **Add inbound webhook**
4. Set permissions: `tasks` (Read and write tasks)
5. Copy the webhook URL

### 2. Set Environment Variable

```bash
export BITRIX_WEBHOOK_URL="https://your-domain.bitrix24.com/rest/1/your-token/"
```

### 3. Configure MCP Client

**Cursor** - Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "uvx",
      "args": ["bitrix24-lkp-mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

**Claude Desktop** - Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "uvx",
      "args": ["bitrix24-lkp-mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

**Claude Code** - Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "uvx",
      "args": ["bitrix24-lkp-mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

**Codex CLI** - Add to `~/.codex/config.toml`:

```toml
[mcp_servers.bitrix24]
command = "uvx"
args = ["bitrix24-lkp-mcp"]
env = { "BITRIX_WEBHOOK_URL" = "https://your-domain.bitrix24.com/rest/1/token/" }
```

## Available Tools

### task_search

Search for tasks by title. Use this to find a task when user provides task name.
Returns matching tasks with `id`, `title`, `responsibleId`, `groupId`, `parentId`, `status`, and `url`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Task title to search for |
| `limit` | int | No | Maximum results (default: 10) |

### task_get

Get detailed information about a task by ID. Returns title, description, assignee, and group.
Also includes `attachmentFileIds` (from Bitrix24 `UF_TASK_WEBDAV_FILES`; empty list if none).
Also includes `stageId` (Kanban stage ID, if the task is in a project with stages; otherwise `null`).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Task ID |
| `includeComments` | bool | No | Include task comments (legacy API via `task.commentitem.getlist`) |

### task_comment_add

Add a comment to a task (via `task.commentitem.add`).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Task ID |
| `message` | string | Yes | Comment text |

### task_create

Create a new task or subtask. Use `parentId` to create a subtask under an existing task.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | Yes | Task title |
| `responsibleId` | int | Yes | Assignee user ID |
| `description` | string | No | Task description |
| `groupId` | int | No | Workgroup/Scrum ID |
| `parentId` | int | No | Parent task ID (creates subtask) |
| `deadline` | string | No | Deadline (ISO 8601) |
| `priority` | string | No | low, medium, high |

### task_update

Update an existing task (via `tasks.task.update`). At least one updatable field must be provided.

Supports:
- Main: title, description, priority, status (accepts common synonyms like "in progress", "done")
- People: assignee (`responsibleId`), participants (`accomplices`), observers (`auditors`)
- Dates: deadline, planned start/end
- Project: group/project, parent task
- Kanban stage: `stageId` (if task is in a project with stages)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Task ID |
| `title` | string | No | Task title |
| `description` | string | No | Task description |
| `priority` | string | No | low, medium, high |
| `status` | string | No | pending, in_progress, completed, deferred (also accepts: "in progress", "done") |
| `responsibleId` | int | No | Assignee user ID |
| `accomplices` | list[int] | No | Participant user IDs |
| `auditors` | list[int] | No | Observer user IDs |
| `deadline` | string | No | Deadline (ISO 8601) |
| `startDatePlan` | string | No | Planned start date (ISO 8601) |
| `endDatePlan` | string | No | Planned end date (ISO 8601) |
| `groupId` | int | No | Workgroup/Project ID |
| `parentId` | int | No | Parent task ID (use 0 to clear) |
| `stageId` | int | No | Kanban stage ID (use 0 to clear) |

### scrum_epic_list

List Scrum epics for a Scrum group (via `tasks.api.scrum.epic.list`). Use this to find `epicId` by epic name.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `groupId` | int | Yes | Scrum group/workgroup ID |
| `query` | string | No | Filter by epic name (case-insensitive substring match) |
| `limit` | int | No | Max results (default: 50) |

### scrum_task_get

Get Scrum-specific fields for a task (via `tasks.api.scrum.task.get`), including `epicId`, `storyPoints`, and `entityId`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Task ID |

### scrum_task_update

Update Scrum fields for an existing task (via `tasks.api.scrum.task.update`).
Supports setting an epic by `epicId` or by `epicName` (resolved within the task's `groupId`).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Task ID |
| `epicId` | int | No | Epic ID (mutually exclusive with `epicName`) |
| `epicName` | string | No | Epic name (mutually exclusive with `epicId`) |
| `storyPoints` | string | No | Story points (string) |
| `entityId` | int | No | Backlog/sprint ID |
| `sort` | int | No | Sorting |

### scrum_task_create

Create a task in a Scrum group and attach Scrum fields.
Internally: creates the base task via `tasks.task.add`, then configures Scrum via `tasks.api.scrum.task.update`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | Yes | Task title |
| `responsibleId` | int | Yes | Assignee user ID |
| `groupId` | int | Yes | Scrum group/workgroup ID |
| `description` | string | No | Task description |
| `deadline` | string | No | Deadline (ISO 8601) |
| `priority` | string | No | low, medium, high |
| `epicId` | int | No | Epic ID (mutually exclusive with `epicName`) |
| `epicName` | string | No | Epic name (mutually exclusive with `epicId`) |
| `storyPoints` | string | No | Story points (string) |
| `entityId` | int | No | Backlog/sprint ID |
| `sort` | int | No | Sorting |

### task_stages_get

Get Scrum board columns (stages) for the **current sprint** of a group/project.

For Scrum groups (`entityId > 0`), this tool fetches the current sprint via `tasks.api.scrum.sprint.list`,
then fetches stages via `tasks.api.scrum.kanban.getStages`.

Returns stages with `id`, `title`, `sort`, `color`, `systemType`, and `sprintId`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entityId` | int | Yes | Scrum group ID; use `0` for current user's "My Planner" stages (fallback) |

### task_stages_move_task

Move a task between kanban/Scrum columns (via `task.stages.movetask`).
Optionally set the task position within the target column using `before` or `after`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Task ID |
| `stageId` | int | Yes | Target stage ID |
| `before` | int | No | Place task before this task ID (mutually exclusive with `after`) |
| `after` | int | No | Place task after this task ID (mutually exclusive with `before`) |

### user_search

Search for users by name. Use this to find a user's ID when you need to assign tasks.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | User name to search for |

### task_list_by_user

List tasks assigned to a specific user.
Returns tasks with `id`, `title`, `responsibleId`, `groupId`, `parentId`, `status`, and `url`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `responsibleId` | int | Yes | User ID |
| `status` | string | No | Filter: pending, in_progress, completed, deferred |
| `limit` | int | No | Maximum results (default: 50) |

### group_search

Search for workgroups/scrums by name. Use this when the user provides a group name (not an ID).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Group name to search for |
| `limit` | int | No | Maximum results (default: 10) |

## Example Usage

```
User: "Plan for task Auto Send welcome email"

AI: [Searches for task, reads description, proposes subtasks]
    
    Based on the task description, here's my proposed plan:
    1. Set up email service configuration
    2. Create welcome email template  
    3. Implement user signup event listener
    4. Implement email sending logic
    
    Ready to create these subtasks?

User: "Yes, create them"

AI: [Creates subtasks with parentId pointing to original task]
    
    Created 4 subtasks under task #456.
```

## Local Development

If you're contributing or running from source:

```bash
git clone https://github.com/lamkimphu258/bitrix24-lkp-mcp.git
cd bitrix24-lkp-mcp

uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

export BITRIX_WEBHOOK_URL="https://your-domain.bitrix24.com/rest/1/token/"
python -m bitrix_mcp
```

To point Cursor at your local checkout, set `command` to your local venv python:

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "/path/to/bitrix24-lkp-mcp/.venv/bin/python",
      "args": ["-m", "bitrix_mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Dependencies

Bitrix24 MCP relies on these libraries:

- `fastmcp` - MCP server framework.
- `httpx` - Async HTTP client.
- `pydantic` - Data validation.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

*Bitrix24 MCP is MIT licensed code.*
