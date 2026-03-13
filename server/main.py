"""BlenderMCP Pro — MCP server entry point.

Uses FastMCP with stdio transport for Claude Desktop integration.
Connects to the Blender addon via TCP.
"""

import asyncio
import logging
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

from server.blender_client import BlenderClient
from server.tool_registry import load_all_tools
from shared.constants import DEFAULT_HOST, DEFAULT_PORT, VERSION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("blendermcp")

# Create the MCP server
mcp = FastMCP("BlenderMCP Pro")

# Create the Blender TCP client
host = os.environ.get("BLENDERMCP_HOST", DEFAULT_HOST)
port = int(os.environ.get("BLENDERMCP_PORT", str(DEFAULT_PORT)))
blender_client = BlenderClient(host, port)


@mcp.resource("blender://status")
async def get_status() -> str:
    """Get BlenderMCP connection status."""
    return f"Connected: {blender_client.is_connected}, Host: {host}:{port}"


# Register all tools
tool_count = load_all_tools(mcp, blender_client)
logger.info(f"BlenderMCP Pro v{VERSION} initialized with {tool_count} tools")


def main():
    """Run the MCP server."""
    logger.info(f"Starting BlenderMCP Pro MCP server (connecting to {host}:{port})")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
