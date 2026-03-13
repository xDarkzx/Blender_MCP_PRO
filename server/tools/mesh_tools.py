from mcp.server.fastmcp import FastMCP
from server.blender_client import BlenderClient


def _screenshot_hint(client: BlenderClient) -> str:
    """Return a hint about the latest auto-screenshot, if any."""
    if client.last_screenshot_path:
        path = client.last_screenshot_path
        client.last_screenshot_path = None  # consume it
        return f"\n[Auto-screenshot: {path}]"
    return ""


def register_tools(mcp: FastMCP, client: BlenderClient) -> int:
    """Register mesh tools with the MCP server. Returns the number of tools registered."""

    @mcp.tool()
    async def mesh_create_primitive(
        type: str,
        name: str = None,
        location: list = None,
        rotation: list = None,
        scale: list = None,
        size: float = None,
        segments: int = None,
        ring_count: int = None,
        radius: float = None,
        vertices: int = None,
        radius1: float = None,
        radius2: float = None,
        depth: float = None,
        major_radius: float = None,
        minor_radius: float = None,
        major_segments: int = None,
        minor_segments: int = None,
        x_subdivisions: int = None,
        y_subdivisions: int = None,
    ) -> str:
        """Create a Blender mesh primitive.

        Supported primitive types and their specific parameters:
          - CUBE: size (side length)
          - UV_SPHERE: segments, ring_count, radius
          - ICO_SPHERE: radius, subdivisions (via segments)
          - CYLINDER: vertices, radius, depth
          - CONE: vertices, radius1 (bottom), radius2 (top), depth
          - TORUS: major_radius, minor_radius, major_segments, minor_segments
          - PLANE: size
          - CIRCLE: vertices, radius
          - GRID: x_subdivisions, y_subdivisions, size

        Common parameters for all types:
          - name: custom object name
          - location: [x, y, z] world position
          - rotation: [x, y, z] rotation in radians
          - scale: [x, y, z] scale factors
        """
        params = {"type": type}
        for key, value in {
            "name": name,
            "location": location,
            "rotation": rotation,
            "scale": scale,
            "size": size,
            "segments": segments,
            "ring_count": ring_count,
            "radius": radius,
            "vertices": vertices,
            "radius1": radius1,
            "radius2": radius2,
            "depth": depth,
            "major_radius": major_radius,
            "minor_radius": minor_radius,
            "major_segments": major_segments,
            "minor_segments": minor_segments,
            "x_subdivisions": x_subdivisions,
            "y_subdivisions": y_subdivisions,
        }.items():
            if value is not None:
                params[key] = value

        result = await client.send_command("mesh.create_primitive", params)
        obj_name = result.get("name", type)
        loc = result.get("location", [0, 0, 0])
        return f"Created {type} primitive '{obj_name}' at location ({loc[0]}, {loc[1]}, {loc[2]})" + _screenshot_hint(client)

    @mcp.tool()
    async def mesh_create_custom(
        vertices: list,
        faces: list,
        edges: list = None,
        name: str = "CustomMesh",
    ) -> str:
        """Create a mesh from raw vertex, edge, and face data.

        Args:
            vertices: list of [x, y, z] vertex positions
            faces: list of vertex index lists defining faces
            edges: optional list of [v1, v2] vertex index pairs defining edges
            name: name for the new mesh object
        """
        params = {"vertices": vertices, "faces": faces, "name": name}
        if edges is not None:
            params["edges"] = edges

        result = await client.send_command("mesh.create_custom", params)
        obj_name = result.get("name", name)
        vert_count = result.get("vertex_count", len(vertices))
        face_count = result.get("face_count", len(faces))
        return f"Created custom mesh '{obj_name}' with {vert_count} vertices and {face_count} faces" + _screenshot_hint(client)

    @mcp.tool()
    async def mesh_edit_geometry(
        object_name: str,
        operation: str = None,
        selection: dict = None,
        steps: list = None,
        offset: float = None,
        thickness: float = None,
        depth: float = None,
        width: float = None,
        segments: int = None,
        cuts: int = None,
        threshold: float = None,
        edge_index: int = None,
        factor: float = None,
        direction: list = None,
        scale_vector: list = None,
        angle: float = None,
        axis: str = None,
        center: list = None,
        delete_type: str = None,
    ) -> str:
        """Perform edit-mode geometry operations on a mesh.

        Can run a single operation OR chain multiple steps in one edit-mode session.

        SINGLE OPERATION: set 'operation' and 'selection'.
        CHAINED OPERATIONS: set 'steps' as a list of step dicts, each with
            'operation', 'selection', and operation-specific params.

        Operations: EXTRUDE, EXTRUDE_ALONG_NORMALS, INSET, BEVEL, SUBDIVIDE,
            DISSOLVE, MERGE, LOOP_CUT, SCALE, TRANSLATE, ROTATE, BRIDGE, FILL,
            SPIN (lathe/revolve - revolve profile around axis, params: steps, angle, axis, center),
            DELETE (remove selected geometry, params: delete_type=VERTS/EDGES/FACES/ONLY_FACE)

        Smart selection (USE THESE instead of guessing face indices!):
            {"type": "face", "position": "top"}      — topmost face(s) by Z
            {"type": "face", "position": "bottom"}   — bottommost face(s) by Z
            {"type": "face", "position": "front"}    — front face(s) (min Y)
            {"type": "face", "position": "back"}     — back face(s) (max Y)
            {"type": "face", "position": "left"}     — left face(s) (min X)
            {"type": "face", "position": "right"}    — right face(s) (max X)
            {"type": "face", "normal": [0,0,1]}      — faces pointing in direction
            {"type": "face", "z_greater": 0.5}       — faces with center above Z
            {"type": "face", "z_less": 0.5}          — faces with center below Z
            {"type": "vert", "z_range": [0.4, 0.6]}  — verts in Z range
            {"type": "vert", "position": "top"}      — topmost verts
            {"type": "face", "indices": "all"}        — all faces
            {"type": "all"}                           — everything

        Example steps for building a lamp post base:
            steps=[
                {"operation": "EXTRUDE", "selection": {"type":"face","position":"top"}, "direction":[0,0,0.1]},
                {"operation": "SCALE", "selection": {"type":"face","position":"top"}, "scale_vector":[0.8,0.8,1]},
                {"operation": "EXTRUDE", "selection": {"type":"face","position":"top"}, "direction":[0,0,0.3]},
                {"operation": "SCALE", "selection": {"type":"face","position":"top"}, "scale_vector":[0.6,0.6,1]},
            ]

        Args:
            object_name: name of the mesh object to edit
            operation: single operation name (not needed if using steps)
            selection: selection dict for single operation
            steps: list of step dicts for chained operations
            offset: distance for extrude operations
            thickness: thickness for inset
            depth: depth for inset
            width: width for bevel
            segments: segments for bevel
            cuts: cuts for loop_cut/subdivide
            edge_index: edge index for loop_cut orientation
            factor: slide factor for loop_cut (-1 to 1)
            direction: [x,y,z] for extrude/translate
            scale_vector: [x,y,z] for scale
            angle: radians for rotate
            axis: X/Y/Z for rotate
        """
        params = {"object_name": object_name}

        if steps is not None:
            params["steps"] = steps
        else:
            if operation:
                params["operation"] = operation
            if selection is not None:
                params["selection"] = selection
            for key, value in {
                "offset": offset, "thickness": thickness, "depth": depth,
                "width": width, "segments": segments, "cuts": cuts,
                "threshold": threshold, "edge_index": edge_index,
                "factor": factor, "direction": direction,
                "scale_vector": scale_vector, "angle": angle, "axis": axis,
                "center": center, "delete_type": delete_type,
            }.items():
                if value is not None:
                    params[key] = value

        result = await client.send_command("mesh.edit_geometry", params)
        verts = result.get("vertex_count", "?")
        edges = result.get("edge_count", "?")
        faces = result.get("face_count", "?")
        success = result.get("success", False)
        step_results = result.get("steps", [])

        lines = []
        for s in step_results:
            op = s.get("operation", "?")
            sel = s.get("selected", 0)
            ok = s.get("success", False)
            err = s.get("error", "")
            status = "OK" if ok else f"FAILED: {err}"
            lines.append(f"  Step {s.get('step',0)}: {op} ({sel} selected) — {status}")

        summary = "\n".join(lines) if lines else "No steps"
        return f"Edit '{object_name}': {verts} verts, {edges} edges, {faces} faces, success={success}\n{summary}" + _screenshot_hint(client)

    @mcp.tool()
    async def mesh_get_geometry(
        object_name: str,
        include_normals: bool = False,
        include_uvs: bool = False,
    ) -> str:
        """Read mesh geometry data from an object.

        Args:
            object_name: name of the mesh object
            include_normals: whether to include vertex normals
            include_uvs: whether to include UV coordinates
        """
        params = {
            "object_name": object_name,
            "include_normals": include_normals,
            "include_uvs": include_uvs,
        }

        result = await client.send_command("mesh.get_geometry", params)
        vertices = result.get("vertices", [])
        faces = result.get("faces", [])
        edges = result.get("edges", [])

        lines = [
            f"Mesh '{object_name}': {len(vertices)} vertices, {len(edges)} edges, {len(faces)} faces",
        ]

        if vertices:
            sample = vertices[:3]
            sample_str = ", ".join(f"({v[0]:.3f}, {v[1]:.3f}, {v[2]:.3f})" for v in sample)
            lines.append(f"  Sample vertices: {sample_str}{'...' if len(vertices) > 3 else ''}")

        if include_normals and "normals" in result:
            normals = result["normals"]
            lines.append(f"  Normals: {len(normals)} entries")

        if include_uvs and "uvs" in result:
            uvs = result["uvs"]
            lines.append(f"  UV layers: {len(uvs)} entries")

        return "\n".join(lines)

    @mcp.tool()
    async def mesh_set_smooth_shading(
        object_name: str,
        smooth: bool = True,
        auto_smooth_angle: float = 30.0,
    ) -> str:
        """Set smooth or flat shading on a mesh object.

        Args:
            object_name: name of the mesh object
            smooth: True for smooth shading, False for flat shading
            auto_smooth_angle: angle threshold in degrees for auto smooth normals
        """
        params = {
            "object_name": object_name,
            "smooth": smooth,
            "auto_smooth_angle": auto_smooth_angle,
        }

        result = await client.send_command("mesh.set_smooth_shading", params)
        mode = "smooth" if smooth else "flat"
        return f"Set '{object_name}' shading to {mode} (auto smooth angle: {auto_smooth_angle}°)" + _screenshot_hint(client)

    @mcp.tool()
    async def mesh_separate(
        object_name: str,
        method: str = "BY_MATERIAL",
    ) -> str:
        """Separate a mesh into multiple objects.

        Args:
            object_name: name of the mesh object to separate
            method: separation method - BY_MATERIAL, BY_LOOSE_PARTS, or BY_SELECTION
        """
        params = {
            "object_name": object_name,
            "method": method,
        }

        result = await client.send_command("mesh.separate", params)
        new_objects = result.get("new_objects", [])
        return f"Separated '{object_name}' by {method}: created {len(new_objects)} new object(s)" + _screenshot_hint(client)

    @mcp.tool()
    async def mesh_join(object_names: list) -> str:
        """Join multiple mesh objects into one.

        Args:
            object_names: list of mesh object names to join (first becomes the target)
        """
        params = {"object_names": object_names}

        result = await client.send_command("mesh.join", params)
        joined_name = result.get("name", object_names[0] if object_names else "unknown")
        return f"Joined {len(object_names)} objects into '{joined_name}'" + _screenshot_hint(client)

    @mcp.tool()
    async def mesh_set_origin(
        object_name: str,
        origin_type: str = "ORIGIN_GEOMETRY",
    ) -> str:
        """Set the origin point of a mesh object.

        Args:
            object_name: name of the mesh object
            origin_type: origin calculation method - ORIGIN_GEOMETRY (geometry to origin),
                         ORIGIN_CENTER_OF_MASS, ORIGIN_CENTER_OF_VOLUME, ORIGIN_CURSOR,
                         GEOMETRY_ORIGIN (origin to geometry)
        """
        params = {
            "object_name": object_name,
            "origin_type": origin_type,
        }

        result = await client.send_command("mesh.set_origin", params)
        return f"Set origin of '{object_name}' using {origin_type}" + _screenshot_hint(client)

    @mcp.tool()
    async def mesh_analyze_profile(
        object_name: str,
        num_slices: int = 20,
    ) -> str:
        """Deep analysis of a mesh object for reverse-engineering construction recipes.

        Analyzes the mesh and returns:
        - Bounding box (min, max, center, dimensions)
        - Z-slice profiles (radius/width at each height level)
        - Material zones (which materials cover which Z ranges)
        - Face normal distribution (up/down/north/south/east/west)
        - Loose parts count (separate mesh islands)
        - Symmetry detection (X and Y axis mirror symmetry)
        - Section identification (distinct parts by radius changes)
        - Modifier stack

        Use this to understand the construction of reference models before
        building similar objects from scratch.

        Args:
            object_name: name of the mesh object to analyze
            num_slices: number of Z-height slices for profile (default 20)
        """
        params = {"object_name": object_name, "num_slices": num_slices}
        result = await client.send_command("mesh.analyze_profile", params)

        lines = [f"=== MESH PROFILE: {result.get('object_name', object_name)} ==="]
        lines.append(f"Geometry: {result.get('vertex_count')} verts, {result.get('edge_count')} edges, {result.get('face_count')} faces")
        lines.append(f"Loose parts: {result.get('loose_parts', '?')}")
        lines.append(f"UVs: {'Yes' if result.get('has_uvs') else 'No'} ({result.get('uv_layer_count', 0)} layers)")

        # Bounding box
        bbox = result.get("bounding_box", {})
        if bbox:
            dims = bbox.get("dimensions", [0,0,0])
            center = bbox.get("center", [0,0,0])
            lines.append(f"\nBOUNDING BOX:")
            lines.append(f"  Dimensions: {dims[0]:.3f} x {dims[1]:.3f} x {dims[2]:.3f}")
            lines.append(f"  Center: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
            lines.append(f"  Min: ({bbox['min'][0]:.3f}, {bbox['min'][1]:.3f}, {bbox['min'][2]:.3f})")
            lines.append(f"  Max: ({bbox['max'][0]:.3f}, {bbox['max'][1]:.3f}, {bbox['max'][2]:.3f})")

        # Symmetry
        sym = result.get("symmetry", {})
        if sym:
            lines.append(f"\nSYMMETRY:")
            lines.append(f"  X-axis: {'YES' if sym.get('x_symmetric') else 'no'} ({sym.get('x_match_ratio', 0):.1%})")
            lines.append(f"  Y-axis: {'YES' if sym.get('y_symmetric') else 'no'} ({sym.get('y_match_ratio', 0):.1%})")

        # Normals
        normals = result.get("face_normal_distribution", {})
        if normals:
            lines.append(f"\nFACE NORMALS:")
            for direction, count in normals.items():
                if count > 0:
                    lines.append(f"  {direction}: {count}")

        # Material zones
        zones = result.get("material_zones", [])
        if zones:
            lines.append(f"\nMATERIAL ZONES ({len(zones)}):")
            for z in zones:
                color_str = ""
                if "base_color_rgb" in z:
                    c = z["base_color_rgb"]
                    color_str = f" RGB({c[0]:.2f},{c[1]:.2f},{c[2]:.2f})"
                lines.append(f"  '{z['material_name']}': {z['face_count']} faces, Z=[{z['z_min']:.3f} to {z['z_max']:.3f}]{color_str}")

        # Sections
        sections = result.get("sections", [])
        if sections:
            lines.append(f"\nSECTIONS ({len(sections)} detected):")
            for i, s in enumerate(sections):
                height = s.get("z_end", 0) - s.get("z_start", 0)
                lines.append(
                    f"  Section {i}: Z=[{s['z_start']:.3f} to {s['z_end']:.3f}] "
                    f"height={height:.3f}, radius=[{s['min_radius']:.3f} to {s['max_radius']:.3f}] "
                    f"avg_r={s['avg_radius']:.3f}"
                )

        # Z-slice profile (compact)
        z_slices = result.get("z_slices", [])
        if z_slices:
            lines.append(f"\nZ-SLICE PROFILE ({len(z_slices)} slices):")
            lines.append(f"  {'Z':>8} | {'R_avg':>7} | {'R_max':>7} | {'W_x':>7} | {'W_y':>7} | Verts")
            lines.append(f"  {'-'*8}-+-{'-'*7}-+-{'-'*7}-+-{'-'*7}-+-{'-'*7}-+------")
            for s in z_slices:
                if s.get("vertex_count", 0) > 0:
                    lines.append(
                        f"  {s['z']:8.3f} | {s.get('radius_avg',0):7.3f} | {s.get('radius_max',0):7.3f} | "
                        f"{s.get('width_x',0):7.3f} | {s.get('width_y',0):7.3f} | {s['vertex_count']}"
                    )
                else:
                    lines.append(f"  {s['z']:8.3f} | {'(gap)':^7} | {'':>7} | {'':>7} | {'':>7} |  0")

        # Modifiers
        mods = result.get("modifiers", [])
        if mods:
            lines.append(f"\nMODIFIERS ({len(mods)}):")
            for m in mods:
                lines.append(f"  {m['name']} ({m['type']})")

        return "\n".join(lines)

    return 9
