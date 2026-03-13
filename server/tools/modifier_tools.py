from mcp.server.fastmcp import FastMCP
from server.blender_client import BlenderClient


def _screenshot_hint(client: BlenderClient) -> str:
    if client.last_screenshot_path:
        path = client.last_screenshot_path
        client.last_screenshot_path = None
        return f"\n[Auto-screenshot: {path}]"
    return ""


def register_tools(mcp: FastMCP, client: BlenderClient) -> int:

    @mcp.tool()
    async def modifier_add(
        object_name: str,
        type: str,
        name: str = None,
        properties: dict = None,
    ) -> str:
        """Add a modifier to a Blender object.

        Common modifier types:
            SUBSURF, MIRROR, ARRAY, BEVEL, BOOLEAN, SOLIDIFY,
            DECIMATE, SMOOTH, EDGE_SPLIT, WIREFRAME, CURVE,
            SHRINKWRAP, SIMPLE_DEFORM, LATTICE, ARMATURE,
            PARTICLE_SYSTEM, OCEAN, CLOTH, COLLISION
        """
        params = {"object_name": object_name, "type": type}
        if name is not None:
            params["name"] = name
        if properties is not None:
            params["properties"] = properties
        result = await client.send_command("modifier.add", params)
        return f"Added modifier '{type}' to '{object_name}': {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def modifier_configure(
        object_name: str, modifier_name: str, properties: dict
    ) -> str:
        """Configure properties of an existing modifier on a Blender object."""
        params = {
            "object_name": object_name,
            "modifier_name": modifier_name,
            "properties": properties,
        }
        result = await client.send_command("modifier.configure", params)
        return f"Configured modifier '{modifier_name}' on '{object_name}': {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def modifier_apply(object_name: str, modifier_name: str) -> str:
        """Apply a modifier to a Blender object, making its effect permanent."""
        params = {"object_name": object_name, "modifier_name": modifier_name}
        result = await client.send_command("modifier.apply", params)
        return f"Applied modifier '{modifier_name}' on '{object_name}': {result}" + _screenshot_hint(client)

    return 3
