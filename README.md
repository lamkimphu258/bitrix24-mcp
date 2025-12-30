# Bitrix24 MCP

**A Model Context Protocol server for Bitrix24 task planning.**

[![PyPI version](https://img.shields.io/pypi/v/bitrix24-lkp-mcp.svg)](https://pypi.org/project/bitrix24-lkp-mcp/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Bitrix24 MCP enables AI assistants to help developers plan and break down tasks into subtasks in Bitrix24 Scrum.

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

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Task title to search for |
| `limit` | int | No | Maximum results (default: 10) |

### task_get

Get detailed information about a task by ID. Returns title, description, assignee, and group.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Task ID |

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
| `priority` | int | No | 0=Low, 1=Medium, 2=High |

### user_search

Search for users by name. Use this to find a user's ID when you need to assign tasks.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | User name to search for |

### task_list_by_user

List tasks assigned to a specific user.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `responsibleId` | int | Yes | User ID |
| `status` | string | No | Filter: pending, in_progress, completed, deferred |
| `limit` | int | No | Maximum results (default: 50) |

### group_get

Get workgroup/scrum details by ID.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | Yes | Group ID |

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
