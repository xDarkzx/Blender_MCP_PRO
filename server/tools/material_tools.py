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
    async def material_create(
        name: str,
        base_color: list,
        metallic: float = 0.0,
        roughness: float = 0.5,
        emission: list = None,
        emission_strength: float = None,
        alpha: float = None,
        blend_mode: str = None,
    ) -> str:
        """Create a new Blender material with PBR properties."""
        params = {
            "name": name,
            "base_color": base_color,
            "metallic": metallic,
            "roughness": roughness,
        }
        if emission is not None:
            params["emission"] = emission
        if emission_strength is not None:
            params["emission_strength"] = emission_strength
        if alpha is not None:
            params["alpha"] = alpha
        if blend_mode is not None:
            params["blend_mode"] = blend_mode
        result = await client.send_command("material.create", params)
        return f"Created material '{name}': {result}"

    @mcp.tool()
    async def material_assign(
        object_name: str, material_name: str, slot_index: int = None
    ) -> str:
        """Assign a material to a Blender object."""
        params = {"object_name": object_name, "material_name": material_name}
        if slot_index is not None:
            params["slot_index"] = slot_index
        result = await client.send_command("material.assign", params)
        return f"Assigned material '{material_name}' to '{object_name}': {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def material_get_info(material_name: str) -> str:
        """Get information about a Blender material."""
        params = {"material_name": material_name}
        result = await client.send_command("material.get_info", params)
        return f"Material info for '{material_name}': {result}"

    @mcp.tool()
    async def material_update(
        material_name: str,
        base_color: list = None,
        metallic: float = None,
        roughness: float = None,
        specular: float = None,
        emission: list = None,
        emission_strength: float = None,
        alpha: float = None,
    ) -> str:
        """Update properties of an existing Blender material."""
        params = {"material_name": material_name}
        if base_color is not None:
            params["base_color"] = base_color
        if metallic is not None:
            params["metallic"] = metallic
        if roughness is not None:
            params["roughness"] = roughness
        if specular is not None:
            params["specular"] = specular
        if emission is not None:
            params["emission"] = emission
        if emission_strength is not None:
            params["emission_strength"] = emission_strength
        if alpha is not None:
            params["alpha"] = alpha
        result = await client.send_command("material.update", params)
        return f"Updated material '{material_name}': {result}" + _screenshot_hint(client)

    return 4
