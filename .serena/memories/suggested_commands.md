# Suggested commands

## Setup
- `uv venv`
- `source .venv/bin/activate`
- `uv pip install -e "./[dev]"`

## Run server
- `export BITRIX_WEBHOOK_URL="https://your-domain.bitrix24.com/rest/1/token/"`
- `python -m bitrix_mcp`

## Lint / format
- `ruff check --fix .`
- `ruff format .`

## Tests
- `pytest -v`
- `pytest tests/test_client.py -v`
- `pytest --cov=src/bitrix_mcp`

## Handy shell
- `ls`, `cd`, `rg`/ripgrep, `find`, `git status`, `git diff`
