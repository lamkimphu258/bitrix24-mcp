# Contributing to Bitrix24 MCP

Contributions are welcome! This guide covers development setup and guidelines.

## Development Setup

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/lamkimphu258/bitrix24-lkp-mcp.git
cd bitrix24-lkp-mcp

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

### Running the Server

```bash
export BITRIX_WEBHOOK_URL="https://your-domain.bitrix24.com/rest/1/token/"
python -m bitrix_mcp
```

### Running Tests

```bash
pytest -v
```

### Linting

```bash
ruff check --fix .
ruff format .
```

## Local Development with Cursor

To test local changes in Cursor, update `~/.cursor/mcp.json`:

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

Replace `/path/to/bitrix-mcp` with the actual path to your cloned repository.

## Project Structure

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
│       └── tools/            # MCP tools
├── tests/
│   ├── conftest.py           # Test fixtures
│   ├── test_client.py        # API client tests
│   ├── test_tools.py         # Tool tests
│   └── test_integration.py   # Workflow tests
├── pyproject.toml
└── README.md
```

## Bitrix24 API Reference

### Task Status Codes

| ID | Status |
|----|--------|
| 2 | Pending |
| 3 | In Progress |
| 4 | Supposedly Completed |
| 5 | Completed |
| 6 | Deferred |

### Priority Levels

| ID | Priority |
|----|----------|
| 0 | Low |
| 1 | Medium |
| 2 | High |

### Rate Limits

- **2 requests per second** - Built-in rate limiting handles this automatically
- Webhook tokens don't expire but can be revoked

## Submitting Changes

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security Notes

- **Never commit your webhook URL** - Use environment variables
- **Webhook permissions** - Only grant necessary permissions (tasks read/write)
- **Revoke if compromised** - You can revoke webhook tokens from Bitrix24 settings

