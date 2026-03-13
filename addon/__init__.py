"""BlenderMCP Pro — Blender addon for AI-driven 3D modeling via MCP.

This addon runs a TCP server inside Blender that receives commands
from the MCP server and executes them using the Blender Python API.
"""

bl_info = {
    "name": "BlenderMCP Pro",
    "author": "BlenderMCP Contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "MCP server for AI-driven 3D modeling",
    "category": "Interface",
}

# Defer imports so Blender can load the module info first
_registered = False


def register():
    global _registered
    if _registered:
        return

    from .preferences import BlenderMCPPreferences
    from . import panels
    from .handlers import register_all_handlers

    import bpy
    bpy.utils.register_class(BlenderMCPPreferences)
    panels.register()
    register_all_handlers()

    # Auto-start if enabled
    from .preferences import get_preferences
    prefs = get_preferences()
    if prefs and prefs.auto_start:
        from .connection import start_server
        start_server(prefs.host, prefs.port)

    _registered = True


def unregister():
    global _registered
    if not _registered:
        return

    from .connection import stop_server
    from .preferences import BlenderMCPPreferences
    from . import panels
    from .handlers import unregister_all_handlers

    stop_server()
    unregister_all_handlers()
    panels.unregister()

    import bpy
    bpy.utils.unregister_class(BlenderMCPPreferences)

    _registered = False
