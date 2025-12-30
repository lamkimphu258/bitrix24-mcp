# Pre-completion checklist

Before considering work done:
1. Add/update tests for any new behavior.
2. Run:
   - `ruff check --fix .`
   - `ruff format .`
3. Run:
   - `pytest -v`
4. If any failures, fix and repeat.
