"""Entry point for the Bitrix24 MCP Server.

This module allows running the server as:
    python -m bitrix_mcp
    uvx bitrix24-lkp-mcp
"""

import argparse
import os
from collections.abc import Mapping
from typing import Any

from .server import mcp

TRANSPORT_CHOICES = ("stdio", "sse", "streamable-http", "http")
HTTP_TRANSPORTS = {"sse", "streamable-http", "http"}
STREAMABLE_HTTP_TRANSPORTS = {"streamable-http", "http"}


def _build_parser() -> argparse.ArgumentParser:
    """Create CLI parser for startup options."""
    parser = argparse.ArgumentParser(
        prog="bitrix24-lkp-mcp",
        description="Run Bitrix24 MCP server",
    )
    parser.add_argument(
        "--transport",
        choices=TRANSPORT_CHOICES,
        help="MCP transport (default: stdio or BITRIX_MCP_TRANSPORT env)",
    )
    parser.add_argument(
        "--host",
        help="HTTP bind host (for sse/streamable-http transports)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="HTTP bind port (for sse/streamable-http transports)",
    )
    parser.add_argument(
        "--path",
        help="HTTP endpoint path (for sse/streamable-http transports)",
    )
    parser.add_argument(
        "--json-response",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use JSON response mode for streamable-http transport",
    )
    parser.add_argument(
        "--stateless-http",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use stateless mode for streamable-http transport",
    )
    return parser


def _parse_env_bool(value: str, *, env_name: str) -> bool:
    """Parse a boolean environment value.

    Args:
        value: Raw environment variable value.
        env_name: Environment variable name for error reporting.

    Returns:
        Parsed boolean value.

    Raises:
        ValueError: If value cannot be parsed as a boolean.
    """
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{env_name} has invalid boolean value {value!r}. Use one of: 1,0,true,false,yes,no,on,off."
    )


def _env_bool(env: Mapping[str, str], env_name: str) -> bool | None:
    """Read an optional boolean from environment."""
    value = env.get(env_name)
    if value is None:
        return None
    return _parse_env_bool(value, env_name=env_name)


def _env_int(env: Mapping[str, str], env_name: str) -> int | None:
    """Read an optional integer from environment."""
    value = env.get(env_name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{env_name} has invalid integer value {value!r}.") from exc


def _resolve_run_config(
    args: argparse.Namespace,
    env: Mapping[str, str],
) -> tuple[str, dict[str, Any]]:
    """Resolve transport and transport kwargs from CLI args and environment.

    Environment variables:
        BITRIX_MCP_TRANSPORT
        BITRIX_MCP_HOST
        BITRIX_MCP_PORT
        BITRIX_MCP_PATH
        BITRIX_MCP_JSON_RESPONSE
        BITRIX_MCP_STATELESS_HTTP
    """
    transport = args.transport or env.get("BITRIX_MCP_TRANSPORT", "stdio")
    if transport not in TRANSPORT_CHOICES:
        raise ValueError(
            f"Unknown transport {transport!r}. Use one of: {', '.join(TRANSPORT_CHOICES)}."
        )

    if transport not in HTTP_TRANSPORTS:
        has_cli_http_option = any(
            option is not None
            for option in (
                args.host,
                args.port,
                args.path,
                args.json_response,
                args.stateless_http,
            )
        )
        if has_cli_http_option:
            raise ValueError(
                "host/port/path/json_response/stateless_http can only be used with "
                "HTTP transports (sse, streamable-http, http)."
            )
        return transport, {}

    host = args.host if args.host is not None else env.get("BITRIX_MCP_HOST")
    port = args.port if args.port is not None else _env_int(env, "BITRIX_MCP_PORT")
    path = args.path if args.path is not None else env.get("BITRIX_MCP_PATH")

    if transport == "sse" and (args.json_response is not None or args.stateless_http is not None):
        raise ValueError(
            "json_response/stateless_http are only supported for streamable-http transport."
        )

    transport_kwargs: dict[str, Any] = {}
    if host is not None:
        transport_kwargs["host"] = host
    if port is not None:
        transport_kwargs["port"] = port
    if path is not None:
        transport_kwargs["path"] = path

    if transport in STREAMABLE_HTTP_TRANSPORTS:
        json_response = (
            args.json_response
            if args.json_response is not None
            else _env_bool(env, "BITRIX_MCP_JSON_RESPONSE")
        )
        stateless_http = (
            args.stateless_http
            if args.stateless_http is not None
            else _env_bool(env, "BITRIX_MCP_STATELESS_HTTP")
        )
        if json_response is not None:
            transport_kwargs["json_response"] = json_response
        if stateless_http is not None:
            transport_kwargs["stateless_http"] = stateless_http

    return transport, transport_kwargs


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        transport, transport_kwargs = _resolve_run_config(args, os.environ)
    except ValueError as exc:
        parser.error(str(exc))

    mcp.run(transport=transport, **transport_kwargs)


if __name__ == "__main__":
    main()
