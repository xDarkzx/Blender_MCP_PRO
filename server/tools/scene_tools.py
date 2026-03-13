"""Scene management tools for BlenderMCP Pro."""

from typing import Optional

from mcp.server.fastmcp import FastMCP
from server.blender_client import BlenderClient


def _format_object_list(objects: list) -> str:
    """Format a list of objects as a readable table."""
    if not objects:
        return "No objects found."

    lines = [f"{'Name':<30} {'Type':<15} {'Visible':<8}"]
    lines.append("-" * 53)
    for obj in objects:
        visible = "Yes" if obj.get("visible", True) else "No"
        lines.append(f"{obj['name']:<30} {obj['type']:<15} {visible:<8}")
    lines.append(f"\nTotal: {len(objects)} object(s)")
    return "\n".join(lines)


def _format_hierarchy(node: dict, indent: int = 0) -> list[str]:
    """Recursively format a hierarchy node as an indented tree."""
    prefix = "  " * indent
    connector = "|- " if indent > 0 else ""
    line = f"{prefix}{connector}{node['name']} [{node.get('type', 'UNKNOWN')}]"
    lines = [line]
    for child in node.get("children", []):
        lines.extend(_format_hierarchy(child, indent + 1))
    return lines


def _format_object_details(obj: dict) -> str:
    """Format full object details as readable text."""
    lines = [
        f"Name: {obj['name']}",
        f"Type: {obj['type']}",
    ]

    if "location" in obj:
        loc = obj["location"]
        lines.append(f"Location: ({loc[0]:.4f}, {loc[1]:.4f}, {loc[2]:.4f})")

    if "rotation" in obj:
        rot = obj["rotation"]
        lines.append(f"Rotation: ({rot[0]:.4f}, {rot[1]:.4f}, {rot[2]:.4f})")

    if "scale" in obj:
        sc = obj["scale"]
        lines.append(f"Scale: ({sc[0]:.4f}, {sc[1]:.4f}, {sc[2]:.4f})")

    if "dimensions" in obj:
        dim = obj["dimensions"]
        lines.append(f"Dimensions: ({dim[0]:.4f}, {dim[1]:.4f}, {dim[2]:.4f})")

    if "visible" in obj:
        lines.append(f"Visible: {'Yes' if obj['visible'] else 'No'}")

    if "parent" in obj:
        lines.append(f"Parent: {obj['parent'] or 'None'}")

    if "children" in obj:
        children = obj["children"]
        lines.append(f"Children: {', '.join(children) if children else 'None'}")

    if "collections" in obj:
        collections = obj["collections"]
        lines.append(f"Collections: {', '.join(collections) if collections else 'None'}")

    if "modifiers" in obj:
        modifiers = obj["modifiers"]
        if modifiers:
            mod_strs = [m["name"] + " (" + m["type"] + ")" if isinstance(m, dict) else str(m) for m in modifiers]
            lines.append(f"Modifiers: {', '.join(mod_strs)}")
        else:
            lines.append("Modifiers: None")

    if "materials" in obj:
        materials = obj["materials"]
        if materials:
            mat_strs = [str(m) if m is not None else "(empty slot)" for m in materials]
            lines.append(f"Materials: {', '.join(mat_strs)}")
        else:
            lines.append("Materials: None")

    mesh_info = obj.get("mesh_info") or obj.get("mesh_stats")
    if mesh_info:
        lines.append(
            f"Mesh: {mesh_info.get('vertex_count', mesh_info.get('vertices', 0))} verts, "
            f"{mesh_info.get('edge_count', mesh_info.get('edges', 0))} edges, "
            f"{mesh_info.get('face_count', mesh_info.get('polygons', 0))} faces"
        )

    return "\n".join(lines)


def register_tools(mcp: FastMCP, client: BlenderClient) -> int:
    """Register scene management tools."""

    @mcp.tool()
    async def scene_get_info() -> str:
        """Get current Blender scene information including name, frame range, FPS, units, object count, and render engine."""
        result = await client.send_command("scene.get_info")
        lines = [
            f"Scene: {result['name']}",
            f"Frame Range: {result['frame_start']}-{result['frame_end']}",
            f"FPS: {result['fps']}",
            f"Units: {result['unit_system']} (scale: {result['unit_scale']})",
            f"Objects: {result['object_count']}",
            f"Render Engine: {result['render_engine']}",
        ]
        return "\n".join(lines)

    @mcp.tool()
    async def scene_list_objects(
        type_filter: Optional[str] = None,
        name_pattern: Optional[str] = None,
        collection: Optional[str] = None,
    ) -> str:
        """List objects in the current Blender scene with optional filtering.

        Args:
            type_filter: Filter by object type (e.g. MESH, LIGHT, CAMERA, CURVE, EMPTY, ARMATURE).
            name_pattern: Filter objects whose name contains this substring (case-insensitive).
            collection: Filter objects belonging to this collection name.
        """
        params = {}
        if type_filter is not None:
            params["type_filter"] = type_filter
        if name_pattern is not None:
            params["name_pattern"] = name_pattern
        if collection is not None:
            params["collection"] = collection

        result = await client.send_command("scene.list_objects", params)
        objects = result if isinstance(result, list) else result.get("objects", [])
        return _format_object_list(objects)

    @mcp.tool()
    async def scene_get_object(name: str) -> str:
        """Get detailed information about a specific object in the Blender scene.

        Args:
            name: The exact name of the object to inspect.
        """
        result = await client.send_command("scene.get_object", {"name": name})
        return _format_object_details(result)

    @mcp.tool()
    async def scene_get_hierarchy(root: Optional[str] = None) -> str:
        """Get the parent-child hierarchy of objects in the scene as an indented tree.

        Args:
            root: Optional root object name. If provided, shows hierarchy starting from that object. If omitted, shows the full scene hierarchy.
        """
        params = {}
        if root is not None:
            params["root"] = root

        result = await client.send_command("scene.get_hierarchy", params)

        # Result is {"hierarchy": [...]} or a list of root nodes
        if isinstance(result, dict) and "hierarchy" in result:
            nodes = result["hierarchy"]
        elif isinstance(result, list):
            nodes = result
        else:
            nodes = [result]

        all_lines = []
        for node in nodes:
            all_lines.extend(_format_hierarchy(node))
        return "\n".join(all_lines) if all_lines else "No objects in hierarchy."

    @mcp.tool()
    async def scene_set_unit_system(
        system: Optional[str] = None,
        scale: Optional[float] = None,
        length_unit: Optional[str] = None,
    ) -> str:
        """Configure the scene unit system and scale.

        Args:
            system: Unit system to use (NONE, METRIC, or IMPERIAL).
            scale: Global scale factor for units.
            length_unit: Length display unit (e.g. KILOMETERS, METERS, CENTIMETERS, MILLIMETERS, MILES, FEET, INCHES).
        """
        params = {}
        if system is not None:
            params["system"] = system
        if scale is not None:
            params["scale"] = scale
        if length_unit is not None:
            params["length_unit"] = length_unit

        result = await client.send_command("scene.set_unit_system", params)

        lines = ["Unit system updated:"]
        if "unit_system" in result:
            lines.append(f"  System: {result['unit_system']}")
        if "unit_scale" in result:
            lines.append(f"  Scale: {result['unit_scale']}")
        if "length_unit" in result:
            lines.append(f"  Length Unit: {result['length_unit']}")
        return "\n".join(lines)

    @mcp.tool()
    async def scene_manage_collection(
        action: str,
        name: str,
        parent: Optional[str] = None,
        new_name: Optional[str] = None,
    ) -> str:
        """Create, delete, or rename a collection in the scene.

        Args:
            action: The action to perform: 'create', 'delete', or 'rename'.
            name: The name of the collection to act on.
            parent: Parent collection name (used with 'create' to nest the new collection).
            new_name: New name for the collection (required for 'rename' action).
        """
        params = {"action": action, "name": name}
        if parent is not None:
            params["parent"] = parent
        if new_name is not None:
            params["new_name"] = new_name

        result = await client.send_command("scene.manage_collection", params)

        message = result.get("message", f"Collection '{name}' {action} completed.")
        return message

    @mcp.tool()
    async def scene_set_active_object(name: str) -> str:
        """Set the active (selected) object in the Blender scene.

        Args:
            name: The exact name of the object to make active.
        """
        result = await client.send_command("scene.set_active_object", {"name": name})

        message = result.get("message", f"Active object set to '{name}'.")
        return message

    return 7  # number of tools registered
