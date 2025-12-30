# bitrix-mcp project overview

## Purpose
Bitrix24 MCP Server: Model Context Protocol (MCP) server that lets AI assistants search Bitrix24 tasks, read task details for analysis, and create/update tasks/subtasks (Scrum/workgroups).

## Tech stack
- Python 3.11+
- MCP SDK: fastmcp
- HTTP client: httpx (async)
- Validation/models: Pydantic v2
- Tests: pytest, pytest-asyncio, respx
- Lint/format: ruff

## High-level architecture
- `src/bitrix_mcp/server.py`: FastMCP server with `@mcp.tool` functions; business logic lives in underscore-prefixed helpers (`_task_get`, etc.) so tests can call them directly.
- `src/bitrix_mcp/bitrix/client.py`: Bitrix24 REST client with a token-bucket rate limiter (2 req/sec) and request/response error handling.
- `src/bitrix_mcp/bitrix/types.py`: Pydantic models + enums + custom exceptions.
- `tests/`: unit + integration tests, respx mocks.

## Conventions
- Bitrix API responses use camelCase keys; Pydantic models map via aliases; tool outputs use camelCase.
- Bitrix IDs come back as strings; convert to int in tool outputs.
