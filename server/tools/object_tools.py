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
    async def object_set_transform(
        name: str,
        location: list = None,
        rotation: list = None,
        scale: list = None,
    ) -> str:
        """Set the transform (location, rotation, scale) of a Blender object."""
        params = {"name": name}
        if location is not None:
            params["location"] = location
        if rotation is not None:
            params["rotation"] = rotation
        if scale is not None:
            params["scale"] = scale
        result = await client.send_command("object.set_transform", params)
        return f"Transform set for '{name}': {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def object_get_transform(name: str, space: str = "WORLD") -> str:
        """Get the transform (location, rotation, scale) of a Blender object."""
        params = {"name": name, "space": space}
        result = await client.send_command("object.get_transform", params)
        return f"Transform for '{name}': {result}"

    @mcp.tool()
    async def object_duplicate(
        name: str,
        linked: bool = False,
        new_name: str = None,
        offset: list = None,
    ) -> str:
        """Duplicate a Blender object."""
        params = {"name": name, "linked": linked}
        if new_name is not None:
            params["new_name"] = new_name
        if offset is not None:
            params["offset"] = offset
        result = await client.send_command("object.duplicate", params)
        return f"Duplicated '{name}': {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def object_delete(names: list, delete_children: bool = False) -> str:
        """Delete one or more Blender objects by name."""
        params = {"names": names, "delete_children": delete_children}
        result = await client.send_command("object.delete", params)
        return f"Deleted objects {names}: {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def object_parent(
        child: str, parent: str, keep_transform: bool = True
    ) -> str:
        """Set the parent of a Blender object."""
        params = {
            "child": child,
            "parent": parent,
            "keep_transform": keep_transform,
        }
        result = await client.send_command("object.parent", params)
        return f"Parented '{child}' to '{parent}': {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def object_unparent(child: str, keep_transform: bool = True) -> str:
        """Remove the parent of a Blender object."""
        params = {"child": child, "keep_transform": keep_transform}
        result = await client.send_command("object.unparent", params)
        return f"Unparented '{child}': {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def object_move_to_collection(name: str, collection: str) -> str:
        """Move a Blender object to a specified collection."""
        params = {"name": name, "collection": collection}
        result = await client.send_command("object.move_to_collection", params)
        return f"Moved '{name}' to collection '{collection}': {result}"

    @mcp.tool()
    async def object_apply_transform(
        name: str,
        location: bool = True,
        rotation: bool = True,
        scale: bool = True,
    ) -> str:
        """Apply the transform of a Blender object, making current transforms the new basis."""
        params = {
            "name": name,
            "location": location,
            "rotation": rotation,
            "scale": scale,
        }
        result = await client.send_command("object.apply_transform", params)
        return f"Applied transform for '{name}': {result}" + _screenshot_hint(client)

    return 8
