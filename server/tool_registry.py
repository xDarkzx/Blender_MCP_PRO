"""Dynamic tool loading and registration for the MCP server."""

import importlib
import logging
from typing import Callable

logger = logging.getLogger("blendermcp.registry")

# List of tool modules to load (Phase 1)
TOOL_MODULES = [
    "server.tools.scene_tools",
    "server.tools.mesh_tools",
    "server.tools.object_tools",
    "server.tools.material_tools",
    "server.tools.modifier_tools",
    "server.tools.viewport_tools",
    "server.tools.selection_tools",
]


def load_all_tools(mcp_server, blender_client) -> int:
    """Load and register all tool modules.

    Each module must have a `register_tools(mcp, client)` function.

    Args:
        mcp_server: The FastMCP server instance
        blender_client: The BlenderClient instance

    Returns:
        Number of tools registered
    """
    total = 0
    for module_name in TOOL_MODULES:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "register_tools"):
                count = module.register_tools(mcp_server, blender_client)
                total += count or 0
                logger.info(f"Loaded {module_name}: {count or '?'} tools")
            else:
                logger.warning(f"Module {module_name} has no register_tools function")
        except Exception as e:
            logger.error(f"Failed to load {module_name}: {e}")

    logger.info(f"Total tools registered: {total}")
    return total
