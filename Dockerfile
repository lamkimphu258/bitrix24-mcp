# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip wheel --wheel-dir /wheels .

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BITRIX_MCP_TRANSPORT=streamable-http \
    BITRIX_MCP_HOST=0.0.0.0 \
    BITRIX_MCP_PORT=8000 \
    BITRIX_MCP_PATH=/mcp

RUN addgroup --system bitrix \
    && adduser --system --ingroup bitrix --home /app bitrix

WORKDIR /app

COPY --from=builder /wheels /wheels

RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

USER bitrix

EXPOSE 8000

CMD ["python", "-m", "bitrix_mcp"]
