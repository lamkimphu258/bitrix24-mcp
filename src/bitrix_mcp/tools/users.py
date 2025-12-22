"""MCP tools for Bitrix24 user management.

This module provides the user_search tool for the MCP server:
- user_search: Find users by name to get their user IDs
"""

import logging
from typing import Any

from ..bitrix.client import Bitrix24Client
from ..bitrix.types import BitrixAPIError, BitrixConnectionError

logger = logging.getLogger(__name__)

# Global client instance - initialized by server
_client: Bitrix24Client | None = None


def set_client(client: Bitrix24Client) -> None:
    """Set the Bitrix24 client instance for tools to use."""
    global _client
    _client = client


def get_client() -> Bitrix24Client:
    """Get the Bitrix24 client instance.

    Raises:
        RuntimeError: If client is not initialized
    """
    if _client is None:
        raise RuntimeError("Bitrix24 client not initialized. Call set_client() first.")
    return _client


async def user_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for users by name.

    Use this tool to find a user's ID when you need to assign tasks.
    The search performs partial matching on name, last name, and email.

    Args:
        query: User name to search for (partial match supported)
        limit: Maximum number of results (default: 10)

    Returns:
        List of matching users with id, name, and email

    Example:
        >>> results = await user_search("John")
        >>> print(results)
        [{"id": 7, "name": "John Doe", "email": "john@company.com"}]
    """
    client = get_client()

    try:
        users = await client.user_get(query=query, limit=limit)
        return [user.to_search_result() for user in users]
    except BitrixConnectionError as e:
        logger.error(f"Connection error during user search: {e}")
        raise RuntimeError(f"Failed to connect to Bitrix24: {e}")
    except BitrixAPIError as e:
        logger.error(f"API error during user search: {e}")
        raise RuntimeError(f"Bitrix24 API error: {e}")

