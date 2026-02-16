"""Tests for CLI startup and transport wiring."""

import pytest

import bitrix_mcp.__main__ as main_module


@pytest.fixture(autouse=True)
def _clear_transport_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure startup transport tests are isolated from local shell env."""
    for name in (
        "BITRIX_MCP_TRANSPORT",
        "BITRIX_MCP_HOST",
        "BITRIX_MCP_PORT",
        "BITRIX_MCP_PATH",
        "BITRIX_MCP_JSON_RESPONSE",
        "BITRIX_MCP_STATELESS_HTTP",
    ):
        monkeypatch.delenv(name, raising=False)


def test_main_defaults_to_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() should default to stdio transport."""
    called: dict[str, object] = {}

    def fake_run(*, transport: str, **kwargs: object) -> None:
        called["transport"] = transport
        called["kwargs"] = kwargs

    monkeypatch.setattr(main_module.mcp, "run", fake_run)

    main_module.main([])

    assert called["transport"] == "stdio"
    assert called["kwargs"] == {}


def test_main_streamable_http_from_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI args should be forwarded to mcp.run for streamable-http."""
    called: dict[str, object] = {}

    def fake_run(*, transport: str, **kwargs: object) -> None:
        called["transport"] = transport
        called["kwargs"] = kwargs

    monkeypatch.setattr(main_module.mcp, "run", fake_run)

    main_module.main(
        [
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--path",
            "/mcp",
            "--json-response",
            "--stateless-http",
        ]
    )

    assert called["transport"] == "streamable-http"
    assert called["kwargs"] == {
        "host": "0.0.0.0",
        "port": 8080,
        "path": "/mcp",
        "json_response": True,
        "stateless_http": True,
    }


def test_main_reads_streamable_http_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should configure HTTP transport when CLI args are absent."""
    called: dict[str, object] = {}

    def fake_run(*, transport: str, **kwargs: object) -> None:
        called["transport"] = transport
        called["kwargs"] = kwargs

    monkeypatch.setattr(main_module.mcp, "run", fake_run)
    monkeypatch.setenv("BITRIX_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("BITRIX_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("BITRIX_MCP_PORT", "9001")
    monkeypatch.setenv("BITRIX_MCP_PATH", "/custom-mcp")
    monkeypatch.setenv("BITRIX_MCP_JSON_RESPONSE", "true")
    monkeypatch.setenv("BITRIX_MCP_STATELESS_HTTP", "false")

    main_module.main([])

    assert called["transport"] == "streamable-http"
    assert called["kwargs"] == {
        "host": "127.0.0.1",
        "port": 9001,
        "path": "/custom-mcp",
        "json_response": True,
        "stateless_http": False,
    }


def test_main_ignores_http_env_options_with_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP env options are ignored when transport remains stdio."""
    called: dict[str, object] = {}

    def fake_run(*, transport: str, **kwargs: object) -> None:
        called["transport"] = transport
        called["kwargs"] = kwargs

    monkeypatch.setattr(main_module.mcp, "run", fake_run)
    monkeypatch.setenv("BITRIX_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("BITRIX_MCP_PORT", "9001")

    main_module.main([])

    assert called["transport"] == "stdio"
    assert called["kwargs"] == {}


def test_main_rejects_http_cli_options_with_stdio() -> None:
    """HTTP-only CLI options should fail when transport is stdio."""
    with pytest.raises(SystemExit):
        main_module.main(["--host", "127.0.0.1"])


def test_main_rejects_invalid_env_bool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid boolean env values should fail fast."""
    monkeypatch.setenv("BITRIX_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("BITRIX_MCP_JSON_RESPONSE", "maybe")

    with pytest.raises(SystemExit):
        main_module.main([])
