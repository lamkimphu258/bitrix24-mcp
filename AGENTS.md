# AGENTS.md

Guidelines for AI agents working with this codebase.

## Project Overview

**Bitrix24 MCP Server** - A Model Context Protocol server enabling AI assistants to help developers plan and break down tasks into subtasks in Bitrix24 Scrum.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.11+ |
| MCP SDK | `mcp` |
| HTTP Client | `httpx` (async) |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio + respx |
| Linting | ruff |

## Project Structure

```
src/bitrix_mcp/
├── __init__.py
├── __main__.py        # Entry point (asyncio.run)
├── server.py          # MCP server, tool definitions, handlers
├── bitrix/
│   ├── client.py      # Bitrix24 API client with rate limiting
│   └── types.py       # Pydantic models, enums, exceptions
└── tools/
    └── tasks.py       # Tool implementations (task_search, task_get, task_create)

tests/
├── conftest.py        # Fixtures (mock responses, webhook URL)
├── test_client.py     # API client tests
├── test_tools.py      # Tool function tests
└── test_integration.py # End-to-end workflow tests
```

## Key Architecture Decisions

### 1. Global Client Pattern
The `Bitrix24Client` is initialized once in `server.py` and shared via `tools/tasks.py`:
```python
# In server.py
client = Bitrix24Client()
tasks.set_client(client)

# In tools/tasks.py
_client: Bitrix24Client | None = None

def get_client() -> Bitrix24Client:
    if _client is None:
        raise RuntimeError("Bitrix24 client not initialized")
    return _client
```

### 2. Rate Limiting
Bitrix24 has a **2 requests/second** limit. The `RateLimiter` class in `client.py` uses a token bucket algorithm to enforce this automatically.

### 3. API Response Handling
- Bitrix24 API returns fields in **camelCase** (e.g., `responsibleId`, `groupId`)
- Pydantic models use `alias` for field mapping
- Tool responses use **camelCase** to match MCP conventions

### 4. Error Handling
Two custom exceptions in `types.py`:
- `BitrixAPIError` - API-level errors (invalid requests, not found)
- `BitrixConnectionError` - Network/timeout errors

Tools catch these and re-raise as `RuntimeError` with user-friendly messages.

## Conventions

### Code Style
- **Line length:** 100 characters (ruff config)
- **Type hints:** Required for all function signatures
- **Docstrings:** Google style with Args/Returns/Raises sections
- **Logging:** Use module-level `logger = logging.getLogger(__name__)`

### Naming
- **Files:** snake_case
- **Classes:** PascalCase
- **Functions/variables:** snake_case
- **API field aliases:** camelCase (matching Bitrix24 API)

### Imports
Order (enforced by ruff):
1. Standard library
2. Third-party (`mcp`, `httpx`, `pydantic`)
3. Local (`from .bitrix.client import ...`)

## Testing

### Run Tests
```bash
# All tests
pytest -v

# Specific file
pytest tests/test_client.py -v

# With coverage
pytest --cov=src/bitrix_mcp
```

### Test Patterns
- **Use `respx`** for mocking HTTP requests to Bitrix24 API
- **Use fixtures** from `conftest.py` for sample responses
- **Test both success and error cases**

Example test structure:
```python
async def test_task_search_success(mock_bitrix_api, sample_task_list_response):
    mock_bitrix_api.post("tasks.task.list").respond(json=sample_task_list_response)
    # ... test logic
```

### Mock Response Format
Always use **camelCase** keys matching actual API:
```python
{
    "id": "456",
    "title": "Task title",
    "responsibleId": "7",
    "groupId": "5",
    "status": "2",
}
```

## Common Operations

### Adding a New Tool
1. Define tool schema in `server.py` `TOOLS` list
2. Implement function in `tools/tasks.py`
3. Add handler in `call_tool()` in `server.py`
4. Add tests in `test_tools.py`

### Modifying Pydantic Models
- Update `types.py`
- Keep `alias` for camelCase API fields
- Update `to_search_result()` / `to_detail_result()` methods if needed
- Update test fixtures in `conftest.py`

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `BITRIX_WEBHOOK_URL` | Yes | Bitrix24 inbound webhook URL |
| `LOG_LEVEL` | No | Logging level (default: `info`) |

## Bitrix24 API Reference

### Task Status Codes
| ID | Status |
|----|--------|
| 2 | pending |
| 3 | in_progress |
| 4 | supposedly_completed |
| 5 | completed |
| 6 | deferred |

### Priority Levels
| ID | Priority |
|----|----------|
| 0 | low |
| 1 | medium |
| 2 | high |

### API Methods Used
| Method | Purpose |
|--------|---------|
| `tasks.task.list` | Search tasks by title filter |
| `tasks.task.get` | Get single task details |
| `tasks.task.add` | Create new task/subtask |

## Development Workflow

### Local Setup
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Running Locally
```bash
# Set webhook URL
export BITRIX_WEBHOOK_URL="https://your-domain.bitrix24.com/rest/1/token/"

# Run server
python -m bitrix_mcp
```

### Testing in Cursor
Update `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "/path/to/bitrix-mcp/.venv/bin/python",
      "args": ["-m", "bitrix_mcp"],
      "env": {
        "BITRIX_WEBHOOK_URL": "https://..."
      }
    }
  }
}
```

## Pre-completion Checklist

**Before implement any task, you MUST:**

1. **Add tests for new features** - Any new functionality must have corresponding test coverage. **Write tests during implementation, not after**:
   - New tools → add tests in `test_tools.py`
   - New API client methods → add tests in `test_client.py`
   - New workflows → add tests in `test_integration.py`

**Before finishing any task, you MUST:**

1. **Run linting/formatting** - Fix all style issues before completing:
   ```bash
   ruff check --fix .
   ruff format .
   ```

2. **Run all tests** - Ensure all tests pass:
   ```bash
   pytest -v
   ```
   If tests fail, fix the issues and repeat steps 2-3 until all tests pass.

**Do NOT consider a task complete until all three steps pass successfully.**

## Gotchas

1. **NEVER read `.env` files** - They contain secrets (webhook tokens). Use environment variables from the system instead.

2. **Bitrix24 returns strings for IDs** - All numeric fields (`id`, `responsibleId`, etc.) come as strings from the API. Pydantic models accept strings and convert to int in output methods.

3. **Rate limiting is per-client** - The `RateLimiter` is instance-bound. Don't create multiple clients.

4. **Webhook URL format** - Must end with `/`. Client auto-appends if missing.

5. **No prompts/resources** - This MCP server only implements tools, not prompts or resources.

6. **asyncio everywhere** - All API operations are async. Use `asyncio.run()` at entry point only.

