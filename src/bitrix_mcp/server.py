"""MCP Server for Bitrix24 task planning.

This server provides tools for AI assistants to help developers
plan and break down tasks into subtasks in Bitrix24 Scrum.
"""

import logging
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .bitrix.client import Bitrix24Client
from .tools import tasks, users

# Configure logging
log_level = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create MCP server instance
server = Server("bitrix24-mcp")


# Tool definitions for MCP
TOOLS = [
    Tool(
        name="task_search",
        description=(
            "Search for tasks by title. Use this to find a task when user provides task name. "
            "Returns matching tasks with id, title, responsibleId, groupId, and status."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Task title to search for (partial match supported)",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum number of results",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="task_get",
        description=(
            "Get detailed information about a task by ID. Returns title, description, "
            "assignee, and group. Use this to read task description for analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "number",
                    "description": "Task ID",
                },
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="task_create",
        description=(
            "Create a new task or subtask. Use parentId to create a subtask under an "
            "existing task. Copy responsibleId and groupId from parent task."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title",
                },
                "description": {
                    "type": "string",
                    "description": "Task description (can include HTML)",
                },
                "responsibleId": {
                    "type": "number",
                    "description": "User ID of assignee (copy from parent task)",
                },
                "groupId": {
                    "type": "number",
                    "description": "Workgroup/Scrum ID (copy from parent task)",
                },
                "parentId": {
                    "type": "number",
                    "description": "Parent task ID - creates this as a SUBTASK",
                },
                "deadline": {
                    "type": "string",
                    "description": "Deadline in ISO 8601 format (optional)",
                },
                "priority": {
                    "type": "number",
                    "enum": [0, 1, 2],
                    "description": "Priority: 0=Low, 1=Medium, 2=High (optional)",
                },
            },
            "required": ["title", "responsibleId"],
        },
    ),
    Tool(
        name="user_search",
        description=(
            "Search for users by name. Use this to find a user's ID when you need to "
            "assign tasks. Returns matching users with id, name, and email."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "User name to search for (partial match supported)",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum number of results",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    import json

    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        if name == "task_search":
            result = await tasks.task_search(
                query=arguments["query"],
                limit=arguments.get("limit", 10),
            )
        elif name == "task_get":
            result = await tasks.task_get(id=arguments["id"])
        elif name == "task_create":
            result = await tasks.task_create(
                title=arguments["title"],
                responsibleId=arguments["responsibleId"],
                description=arguments.get("description"),
                groupId=arguments.get("groupId"),
                parentId=arguments.get("parentId"),
                deadline=arguments.get("deadline"),
                priority=arguments.get("priority"),
            )
        elif name == "user_search":
            result = await users.user_search(
                query=arguments["query"],
                limit=arguments.get("limit", 10),
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    # Initialize Bitrix24 client
    try:
        client = Bitrix24Client()
        tasks.set_client(client)
        users.set_client(client)
        logger.info("Bitrix24 client initialized successfully")
    except ValueError as e:
        logger.error(f"Failed to initialize Bitrix24 client: {e}")
        raise

    # Run server
    logger.info("Starting Bitrix24 MCP server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

