"""MCP tool modules for BlenderMCP Pro."""

from server.blender_client import BlenderClient


def screenshot_hint(client: BlenderClient) -> str:
    """Return a hint about the latest auto-screenshot path, if any.

    Call this at the end of any scene-modifying tool's return string.
    Consumes the path so it's only reported once.
    """
    if client.last_screenshot_path:
        path = client.last_screenshot_path
        client.last_screenshot_path = None
        return f"\n[Auto-screenshot: {path}]"
    return ""
