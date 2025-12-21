"""Entry point for the Bitrix24 MCP Server.

This module allows running the server as:
    python -m bitrix_mcp
    uvx bitrix24-mcp
"""

import asyncio

from .server import run_server


def main() -> None:
    """Main entry point."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()

