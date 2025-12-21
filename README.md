# Bitrix24 MCP Server

<div align="center">

**AI-powered task planning for Bitrix24 Scrum**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-brightgreen.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI assistants to help developers plan and break down tasks into subtasks in Bitrix24 Scrum.

## ✨ Features

- **🔍 Task Search** - Find tasks by title with partial matching
- **📋 Task Details** - Get full task information including description for AI analysis
- **➕ Subtask Creation** - Create subtasks under parent tasks automatically
- **⚡ Rate Limited** - Respects Bitrix24's 2 requests/second limit
- **🔐 Secure** - Uses Bitrix24 inbound webhooks for authentication

## 🎯 Use Case

```
👤 User: "Plan for task Auto Send welcome email"
       ↓
🤖 AI finds task → Reads description → Proposes subtasks
       ↓
👤 User reviews → Gives feedback → Approves
       ↓
✅ Creates subtasks automatically in Bitrix24
```

## 📦 Installation

### Using uvx (Recommended)

```bash
uvx bitrix24-mcp
```

### Using pip

```bash
pip install bitrix24-mcp
```

### From Source

```bash
git clone https://github.com/yourusername/bitrix-mcp.git
cd bitrix-mcp
pip install -e .
```

## ⚙️ Configuration

### 1. Create Bitrix24 Webhook

1. Go to your Bitrix24 portal
2. Navigate to **Developer resources** → **Other** → **Inbound webhook**
3. Click **Add inbound webhook**
4. Set permissions:
   - ✅ `tasks` - Read and write tasks
5. Copy the webhook URL (format: `https://your-domain.bitrix24.com/rest/1/token/`)

### 2. Set Environment Variable

```bash
export BITRIX_WEBHOOK_URL="https://your-domain.bitrix24.com/rest/1/your-webhook-token/"
```

Or create a `.env` file:

```env
BITRIX_WEBHOOK_URL=https://your-domain.bitrix24.com/rest/1/your-webhook-token/
LOG_LEVEL=info
```

### 3. Configure MCP Client

#### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "uvx",
      "args": ["bitrix24-mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "uvx",
      "args": ["bitrix24-mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

## 🛠️ Available Tools

### `task_search`

Search for tasks by title (partial match supported).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | ✅ | Task title to search for |
| `limit` | number | ❌ | Maximum results (default: 10) |

**Example:**
```
🔧 task_search(query="welcome email")

📤 Output:
[
  {
    "id": 456,
    "title": "Auto Send welcome email",
    "responsibleId": 7,
    "groupId": 5,
    "status": "pending"
  }
]
```

### `task_get`

Get detailed information about a task by ID.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | number | ✅ | Task ID |

**Example:**
```
🔧 task_get(id=456)

📤 Output:
{
  "id": 456,
  "title": "Auto Send welcome email",
  "description": "Any new sign up user, send welcome email.",
  "responsibleId": 7,
  "groupId": 5,
  "status": "pending",
  "priority": "medium",
  "deadline": null,
  "parentId": null,
  "createdBy": 1
}
```

### `task_create`

Create a new task or subtask.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | ✅ | Task title |
| `responsibleId` | number | ✅ | Assignee user ID |
| `description` | string | ❌ | Task description (HTML supported) |
| `groupId` | number | ❌ | Workgroup/Scrum ID |
| `parentId` | number | ❌ | Parent task ID (creates subtask) |
| `deadline` | string | ❌ | Deadline (ISO 8601 format) |
| `priority` | number | ❌ | 0=Low, 1=Medium, 2=High |

**Example:**
```
🔧 task_create(
  title="Set up email service",
  description="Configure SMTP or email service",
  responsibleId=7,
  groupId=5,
  parentId=456
)

📤 Output:
{
  "id": 457,
  "title": "Set up email service"
}
```

## 📖 Example Workflow

### Complete Planning Session

```
👤 User: "Plan for task Auto Send welcome email"

🤖 AI: Let me find that task...
   [Calls task_search(query="Auto Send welcome email")]
   
   Found task #456. Let me get the details...
   [Calls task_get(id=456)]
   
   Based on the description "Any new sign up user, send welcome email",
   here's my proposed plan:
   
   1. Set up email service configuration
      Configure SMTP or email service (SendGrid/AWS SES)
      
   2. Create welcome email template
      Design HTML template with welcome message
      
   3. Implement user signup event listener
      Set up event to trigger on new registration
      
   4. Implement email sending logic
      Create service to send email when event fires
      
   Does this look good?

👤 User: "Add a task for unit testing"

🤖 AI: Updated. Added:
   5. Write unit tests
      Test email service, template rendering, and event handling
      
   Ready to create these subtasks?

👤 User: "Yes, create them"

🤖 AI: Creating subtasks...
   [Calls task_create for each subtask with parentId=456]
   
   ✅ Created 5 subtasks:
   - #457: Set up email service configuration
   - #458: Create welcome email template
   - #459: Implement user signup event listener
   - #460: Implement email sending logic
   - #461: Write unit tests
   
   All assigned to the same person and group as the parent task.
```

## 🧪 Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/bitrix-mcp.git
cd bitrix-mcp

# Create virtual environment using uv (recommended)
uv venv
source .venv/bin/activate

# Install with dev dependencies
uv pip install -e ".[dev]"
```

**Alternative with pip:**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure Cursor for Local Development

To test your local changes in Cursor, update `~/.cursor/mcp.json` to use the local Python interpreter:

```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "/path/to/bitrix-mcp/.venv/bin/python",
      "args": ["-m", "bitrix_mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://your-domain.bitrix24.com/rest/1/token/"
      }
    }
  }
}
```

> **Note:** Replace `/path/to/bitrix-mcp` with the actual path to your cloned repository.

### Running the Server Manually

```bash
python -m bitrix_mcp
```

### Running Tests

```bash
pytest -v
```

### Project Structure

```
bitrix-mcp/
├── src/
│   └── bitrix_mcp/
│       ├── __init__.py
│       ├── __main__.py       # Entry point
│       ├── server.py         # MCP server setup
│       ├── bitrix/
│       │   ├── client.py     # API client with rate limiting
│       │   └── types.py      # Pydantic models
│       └── tools/
│           └── tasks.py      # MCP tools implementation
├── tests/
│   ├── conftest.py           # Test fixtures
│   ├── test_client.py        # API client tests
│   ├── test_tools.py         # Tool tests
│   └── test_integration.py   # Workflow tests
├── pyproject.toml
├── tasks.md                  # Implementation tasks
└── README.md
```

## 📊 Bitrix24 API Reference

### Task Status Codes

| Status ID | Status |
|-----------|--------|
| 2 | Pending |
| 3 | In Progress |
| 4 | Supposedly Completed |
| 5 | Completed |
| 6 | Deferred |

### Priority Levels

| Priority | Level |
|----------|-------|
| 0 | Low |
| 1 | Medium |
| 2 | High |

### Rate Limits

- **2 requests per second** - Built-in rate limiting handles this automatically
- Webhook tokens don't expire but can be revoked

## 🔒 Security Notes

- **Never commit your webhook URL** - Use environment variables
- **Webhook permissions** - Only grant necessary permissions (tasks read/write)
- **Revoke if compromised** - You can revoke webhook tokens from Bitrix24 settings

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

<div align="center">
Made with ❤️ for Bitrix24 developers
</div>

