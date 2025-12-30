# Style & conventions

- Line length: 100 (ruff)
- Type hints required for all function signatures.
- Docstrings: Google style (Args/Returns/Raises).
- Logging: module-level `logger = logging.getLogger(__name__)`.
- Naming:
  - files: snake_case
  - classes: PascalCase
  - functions/vars: snake_case
  - API field aliases / tool output keys: camelCase
- Import order (ruff): stdlib, third-party, local.
- Async everywhere for API operations.
- Tests should call underscore-prefixed helpers in `server.py` (e.g. `_task_get`) instead of `@mcp.tool` wrappers.
