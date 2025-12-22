# Tasks

## Migrate to FastMCP

Refactor from low-level MCP SDK to FastMCP decorator-based approach.

### Tasks

- [ ] **Update `pyproject.toml`**
  - Replace `mcp>=1.0.0` with `fastmcp>=2.0.0`

- [ ] **Rewrite `server.py` with FastMCP**
  - Replace `Server` with `FastMCP`
  - Initialize `Bitrix24Client` at module level (singleton pattern)
  - Remove manual `TOOLS` list (~100 lines)
  - Remove `@server.list_tools()` handler
  - Remove `@server.call_tool()` handler with if/elif routing

- [ ] **Add `@mcp.tool` decorated functions** (inline in `server.py`)
  - `task_search(query: str, limit: int = 10) -> list[dict]`
  - `task_get(id: int) -> dict`
  - `task_create(title, responsibleId, description?, groupId?, parentId?, deadline?, priority?) -> dict`
  - `user_search(query: str, limit: int = 10) -> list[dict]`
  - Return dicts directly (FastMCP handles JSON serialization)

- [ ] **Update `__main__.py`**
  - Replace `asyncio.run(run_server())` with `mcp.run()`

- [ ] **Delete obsolete files**
  - `tools/tasks.py`
  - `tools/users.py`
  - `tools/__init__.py`

- [ ] **Update tests**
  - `test_tools.py` - import tools from `server.py`, call functions directly
  - `test_integration.py` - same pattern, no `set_client()` needed
  - Pass mock client directly or use module-level client override

- [ ] **Update `AGENTS.md`**
  - Document FastMCP architecture
  - Update "Adding a New Tool" section
  - Update project structure (no `tools/` folder)

- [ ] **Run linting and tests**
  - `ruff check --fix .`
  - `ruff format .`
  - `pytest -v`

### Example: New `server.py` Structure

```python
from fastmcp import FastMCP
from .bitrix.client import Bitrix24Client
from .bitrix.types import BitrixAPIError, BitrixConnectionError

mcp = FastMCP("bitrix24-mcp")

# Module-level client (initialized on first use)
_client: Bitrix24Client | None = None

def get_client() -> Bitrix24Client:
    global _client
    if _client is None:
        _client = Bitrix24Client()
    return _client

@mcp.tool
async def task_search(query: str, limit: int = 10) -> list[dict]:
    """Search for tasks by title."""
    client = get_client()
    tasks = await client.task_list(filter={"%TITLE": query}, limit=limit)
    return [task.to_search_result() for task in tasks]

# ... more tools ...
```

### Files Changed

| File | Action |
|------|--------|
| `pyproject.toml` | Update dependency |
| `server.py` | Major refactor |
| `__main__.py` | Minor update |
| `tools/tasks.py` | Delete |
| `tools/users.py` | Delete |
| `tools/__init__.py` | Delete |
| `tests/test_tools.py` | Update |
| `tests/test_integration.py` | Update |
| `AGENTS.md` | Update |

### Files Unchanged

- `bitrix/client.py` - API client stays the same
- `bitrix/types.py` - Pydantic models stay the same
- `tests/conftest.py` - Fixtures stay the same
- `tests/test_client.py` - Client tests stay the same
