from mcp.server.fastmcp import FastMCP
from server.blender_client import BlenderClient


def register_tools(mcp: FastMCP, client: BlenderClient) -> int:

    @mcp.tool()
    async def selection_set(
        names: list = None,
        type_filter: str = None,
        pattern: str = None,
        action: str = "SET",
    ) -> str:
        """Set the selection of objects in Blender.

        Args:
            names: List of object names to select.
            type_filter: Filter by object type (e.g. MESH, CURVE, LIGHT).
            pattern: Glob pattern to match object names.
            action: Selection action - SET, ADD, REMOVE, TOGGLE, DESELECT_ALL.
        """
        params = {"action": action}
        if names is not None:
            params["names"] = names
        if type_filter is not None:
            params["type_filter"] = type_filter
        if pattern is not None:
            params["pattern"] = pattern
        result = await client.send_command("selection.set", params)
        return f"Selection updated (action={action}): {result}"

    return 1
