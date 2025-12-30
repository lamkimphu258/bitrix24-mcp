# PyPI Publishing Guide

Step-by-step guide to publish `bitrix24-mcp` to PyPI.

---

## Prerequisites

### 1. Fill Placeholders

Update these files with your information:

**pyproject.toml:**
```toml
authors = [
    { name = "Your Name", email = "your@email.com" }
]

[project.urls]
Homepage = "https://github.com/yourusername/bitrix-mcp"
Repository = "https://github.com/yourusername/bitrix-mcp"
Issues = "https://github.com/yourusername/bitrix-mcp/issues"
```

**LICENSE:**
```
Copyright (c) 2025 Your Name
```

### 2. Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Verify your email
3. Enable 2FA (recommended)

### 3. Create API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Token name: `bitrix24-mcp` (or any name)
4. Scope: "Entire account" (for first upload) or project-specific after
5. Copy the token (starts with `pypi-`)

---

## Pre-Publishing Checklist

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run linting
ruff check --fix .
ruff format .

# 3. Run tests
pytest -v

# 4. Verify all tests pass before continuing
```

---

## Build the Package

```bash
# Install build tools
pip install build twine

# Build package (creates dist/ folder)
python -m build
```

This creates two files in `dist/`:
- `bitrix24_mcp-1.0.0.tar.gz` (source distribution)
- `bitrix24_mcp-1.0.0-py3-none-any.whl` (wheel)

---

## Test on TestPyPI (Optional but Recommended)

### 1. Create TestPyPI Account

1. Go to https://test.pypi.org/account/register/
2. Create a separate API token at https://test.pypi.org/manage/account/token/

### 2. Upload to TestPyPI

```bash
twine upload --repository testpypi dist/*
```

When prompted:
- Username: `__token__`
- Password: Your TestPyPI API token

### 3. Test Installation

```bash
pip install -i https://test.pypi.org/simple/ bitrix24-mcp
```

---

## Publish to Production PyPI

### Option A: Interactive (prompted for credentials)

```bash
twine upload dist/*
```

When prompted:
- Username: `__token__`
- Password: Your PyPI API token (the one starting with `pypi-`)

### Option B: Using Environment Variable

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your-token-here

twine upload dist/*
```

### Option C: Using .pypirc File

Create `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-your-token-here
```

Then:

```bash
twine upload dist/*
```

> **Security Note:** If using `.pypirc`, set permissions: `chmod 600 ~/.pypirc`

---

## Post-Publishing

### 1. Verify Package Page

Visit: https://pypi.org/project/bitrix24-mcp/

### 2. Test Installation

```bash
# Create fresh environment
python -m venv test-env
source test-env/bin/activate

# Install from PyPI
pip install bitrix24-mcp

# Test it works
bitrix24-mcp --help
```

### 3. Test with uvx

```bash
uvx bitrix24-mcp
```

---

## Publishing Updates

When releasing a new version:

### 1. Update Version

Update version in both files:

**pyproject.toml:**
```toml
version = "1.0.1"
```

**src/bitrix_mcp/__init__.py:**
```python
__version__ = "1.0.1"
```

### 2. Clean Old Builds

```bash
rm -rf dist/ build/ *.egg-info
```

### 3. Build and Upload

```bash
python -m build
twine upload dist/*
```

---

## Troubleshooting

### "File already exists"

You cannot upload the same version twice. Bump the version number.

### "Invalid token"

- Make sure you're using `__token__` as username (literally)
- Token must start with `pypi-`
- Check if token has correct scope

### "Package name already taken"

Someone else has registered `bitrix24-mcp`. Choose a different name in `pyproject.toml`.

### Build fails

```bash
# Clean and rebuild
rm -rf dist/ build/ *.egg-info src/*.egg-info
python -m build
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python -m build` | Build package |
| `twine check dist/*` | Validate package |
| `twine upload --repository testpypi dist/*` | Upload to TestPyPI |
| `twine upload dist/*` | Upload to PyPI |

---

## Links

- PyPI: https://pypi.org/
- TestPyPI: https://test.pypi.org/
- Python Packaging Guide: https://packaging.python.org/
- Twine Documentation: https://twine.readthedocs.io/

