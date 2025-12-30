"""Entry point for the Bitrix24 MCP Server.

This module allows running the server as:
    python -m bitrix_mcp
    uvx bitrix24-lkp-mcp
"""

from .server import mcp


def main() -> None:
    """Main entry point."""
    mcp.run()


if __name__ == "__main__":
    main()
