"""
Mesh tool handlers for BlenderMCP.

Provides 8 mesh operations: create_primitive, create_custom, edit_geometry,
get_geometry, set_smooth_shading, separate, join, and set_origin.
"""

import math

try:
    import bpy
    import bmesh
except ImportError:
    bpy = None
    bmesh = None

try:
    from ..dispatcher import register_handler
    from ..validation import (
        validate_params,
        validate_object_name,
        validate_vertices,
        validate_faces,
        validate_vector3,
    )
    from ..shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from addon.dispatcher import register_handler
    from addon.validation import (
        validate_params,
        validate_object_name,
        validate_vertices,
        validate_faces,
        validate_vector3,
    )
    from shared.error_codes import ErrorCode, BlenderMCPError


# ---------------------------------------------------------------------------
# 1. mesh.create_primitive
# ---------------------------------------------------------------------------

def handle_create_primitive(params):
    """Create a mesh primitive of the specified type."""
    if not params.get("type"):
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: type")

    prim_type = params["type"].upper()
    location = tuple(params.get("location", [0, 0, 0]))
    rotation = tuple(params.get("rotation", [0, 0, 0]))
    scale = tuple(params.get("scale", [1, 1, 1]))
    name = params.get("name", None)

    validate_vector3(location, "location")
    validate_vector3(rotation, "rotation")
    validate_vector3(scale, "scale")

    valid_types = {
        "CUBE", "SPHERE", "CYLINDER", "CONE", "TORUS", "PLANE", "GRID", "MONKEY",
    }
    if prim_type not in valid_types:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Invalid primitive type '{prim_type}'. Must be one of {sorted(valid_types)}",
        )

    if prim_type == "CUBE":
        size = params.get("size", 2)
        bpy.ops.mesh.primitive_cube_add(
            size=size, location=location, rotation=rotation, scale=scale,
        )
    elif prim_type == "SPHERE":
        segments = params.get("segments", 32)
        ring_count = params.get("ring_count", 16)
        radius = params.get("radius", 1)
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=segments,
            ring_count=ring_count,
            radius=radius,
            location=location,
            rotation=rotation,
            scale=scale,
        )
    elif prim_type == "CYLINDER":
        vertices = params.get("vertices", 32)
        radius = params.get("radius", params.get("radius1", 1))
        depth = params.get("depth", 2)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=vertices,
            radius=radius,
            depth=depth,
            location=location,
            rotation=rotation,
            scale=scale,
        )
    elif prim_type == "CONE":
        vertices = params.get("vertices", 32)
        radius1 = params.get("radius1", 1)
        radius2 = params.get("radius2", 0)
        depth = params.get("depth", 2)
        bpy.ops.mesh.primitive_cone_add(
            vertices=vertices,
            radius1=radius1,
            radius2=radius2,
            depth=depth,
            location=location,
            rotation=rotation,
            scale=scale,
        )
    elif prim_type == "TORUS":
        major_radius = params.get("major_radius", 1)
        minor_radius = params.get("minor_radius", 0.25)
        major_segments = params.get("major_segments", 48)
        minor_segments = params.get("minor_segments", 12)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=major_radius,
            minor_radius=minor_radius,
            major_segments=major_segments,
            minor_segments=minor_segments,
            location=location,
            rotation=rotation,
            # torus does not accept scale in the operator directly
        )
        bpy.context.active_object.scale = scale
    elif prim_type == "PLANE":
        size = params.get("size", 2)
        bpy.ops.mesh.primitive_plane_add(
            size=size, location=location, rotation=rotation, scale=scale,
        )
    elif prim_type == "GRID":
        x_subdivisions = params.get("x_subdivisions", 10)
        y_subdivisions = params.get("y_subdivisions", 10)
        size = params.get("size", 2)
        bpy.ops.mesh.primitive_grid_add(
            x_subdivisions=x_subdivisions,
            y_subdivisions=y_subdivisions,
            size=size,
            location=location,
            rotation=rotation,
            scale=scale,
        )
    elif prim_type == "MONKEY":
        bpy.ops.mesh.primitive_monkey_add(
            location=location, rotation=rotation, scale=scale,
        )

    obj = bpy.context.active_object
    if name:
        obj.name = name
        obj.data.name = name

    mesh = obj.data
    return {
        "name": obj.name,
        "type": prim_type,
        "location": list(obj.location),
        "vertex_count": len(mesh.vertices),
        "face_count": len(mesh.polygons),
    }


# ---------------------------------------------------------------------------
# 2. mesh.create_custom
# ---------------------------------------------------------------------------

def handle_create_custom(params):
    """Create a mesh from raw vertex, edge, and face data."""
    for req in ("vertices", "faces", "name"):
        if req not in params:
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, f"Missing required parameter: {req}")

    vertices = params["vertices"]
    faces = params["faces"]
    edges = params.get("edges", [])
    name = params["name"]

    validate_vertices(vertices)
    validate_faces(faces, len(vertices))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, edges, faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    return {
        "name": obj.name,
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "face_count": len(mesh.polygons),
    }


# ---------------------------------------------------------------------------
# 3. mesh.edit_geometry
# ---------------------------------------------------------------------------

def _face_center_z(face):
    """Get the average Z of a face's vertices."""
    return sum(v.co.z for v in face.verts) / len(face.verts)


def _face_center(face):
    """Get the center point of a face."""
    n = len(face.verts)
    return (
        sum(v.co.x for v in face.verts) / n,
        sum(v.co.y for v in face.verts) / n,
        sum(v.co.z for v in face.verts) / n,
    )


def _select_geometry(bm, selection):
    """Parse selection dict and select geometry in bmesh.

    Supports:
      - {"type": "face", "indices": [0,1,2]}   — specific indices
      - {"type": "face", "indices": "all"}      — all faces
      - {"type": "face", "range": [4, 10]}      — index range [start, end)
      - {"type": "all"}                         — everything

      Smart selection (faces only):
      - {"type": "face", "position": "top"}     — face(s) with highest avg Z
      - {"type": "face", "position": "bottom"}  — face(s) with lowest avg Z
      - {"type": "face", "position": "front"}   — face(s) with lowest avg Y
      - {"type": "face", "position": "back"}    — face(s) with highest avg Y
      - {"type": "face", "position": "left"}    — face(s) with lowest avg X
      - {"type": "face", "position": "right"}   — face(s) with highest avg X
      - {"type": "face", "normal": [0,0,1]}     — faces whose normal aligns with vector (dot > 0.9)
      - {"type": "face", "normal": [0,0,1], "threshold": 0.5}  — custom dot threshold
      - {"type": "face", "z_greater": 0.5}      — faces with center Z > value
      - {"type": "face", "z_less": 0.5}         — faces with center Z < value

      Vertex smart selection:
      - {"type": "vert", "position": "top"}     — verts at max Z
      - {"type": "vert", "z_greater": 0.5}      — verts with Z > value
      - {"type": "vert", "z_range": [0.4, 0.6]} — verts with Z in range

    Returns (selection_type_string, count_selected).
    """
    # Deselect all first
    for v in bm.verts:
        v.select = False
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False

    sel_type = selection.get("type", "VERT").upper()
    count = 0

    # Select everything shortcut
    if sel_type == "ALL":
        for v in bm.verts:
            v.select = True
        for e in bm.edges:
            e.select = True
        for f in bm.faces:
            f.select = True
        bm.select_flush(True)
        # Return the most relevant type based on what exists
        if bm.faces:
            return "FACE", len(bm.faces)
        elif bm.edges:
            return "EDGE", len(bm.edges)
        else:
            return "VERT", len(bm.verts)

    # ------- SMART SELECTION: POSITION-BASED -------
    position = selection.get("position")
    normal_dir = selection.get("normal")
    z_greater = selection.get("z_greater")
    z_less = selection.get("z_less")
    z_range = selection.get("z_range")

    if sel_type == "FACE" and (position or normal_dir is not None or z_greater is not None or z_less is not None):
        if position:
            position = position.upper()
            # Calculate center Z/X/Y for each face
            if position == "TOP":
                max_z = max(_face_center_z(f) for f in bm.faces)
                for f in bm.faces:
                    if abs(_face_center_z(f) - max_z) < 0.0001:
                        f.select = True
                        count += 1
            elif position == "BOTTOM":
                min_z = min(_face_center_z(f) for f in bm.faces)
                for f in bm.faces:
                    if abs(_face_center_z(f) - min_z) < 0.0001:
                        f.select = True
                        count += 1
            elif position in ("FRONT", "BACK", "LEFT", "RIGHT"):
                axis_map = {"FRONT": (1, min), "BACK": (1, max), "LEFT": (0, min), "RIGHT": (0, max)}
                axis_idx, func = axis_map[position]
                centers = [_face_center(f) for f in bm.faces]
                target_val = func(c[axis_idx] for c in centers)
                for f, c in zip(bm.faces, centers):
                    if abs(c[axis_idx] - target_val) < 0.0001:
                        f.select = True
                        count += 1

        elif normal_dir is not None:
            from mathutils import Vector
            target = Vector(normal_dir).normalized()
            threshold = selection.get("threshold", 0.9)
            for f in bm.faces:
                if f.normal.dot(target) > threshold:
                    f.select = True
                    count += 1

        elif z_greater is not None:
            for f in bm.faces:
                if _face_center_z(f) > z_greater:
                    f.select = True
                    count += 1

        elif z_less is not None:
            for f in bm.faces:
                if _face_center_z(f) < z_less:
                    f.select = True
                    count += 1

        bm.select_flush(True)
        return "FACE", count

    # ------- SMART SELECTION: VERTS BY POSITION -------
    if sel_type == "VERT" and (position or z_greater is not None or z_less is not None or z_range):
        if position:
            position = position.upper()
            if position == "TOP":
                max_z = max(v.co.z for v in bm.verts)
                for v in bm.verts:
                    if abs(v.co.z - max_z) < 0.0001:
                        v.select = True
                        count += 1
            elif position == "BOTTOM":
                min_z = min(v.co.z for v in bm.verts)
                for v in bm.verts:
                    if abs(v.co.z - min_z) < 0.0001:
                        v.select = True
                        count += 1
        elif z_greater is not None:
            for v in bm.verts:
                if v.co.z > z_greater:
                    v.select = True
                    count += 1
        elif z_less is not None:
            for v in bm.verts:
                if v.co.z < z_less:
                    v.select = True
                    count += 1
        elif z_range:
            lo, hi = float(z_range[0]), float(z_range[1])
            for v in bm.verts:
                if lo <= v.co.z <= hi:
                    v.select = True
                    count += 1

        bm.select_flush(True)
        return "VERT", count

    # ------- INDEX-BASED SELECTION -------
    sel_indices = selection.get("indices", [])
    sel_range_val = selection.get("range")

    if sel_type == "VERT":
        elements = bm.verts
    elif sel_type == "EDGE":
        elements = bm.edges
    elif sel_type == "FACE":
        elements = bm.faces
    else:
        elements = bm.verts

    if sel_indices == "all" or sel_indices == "ALL":
        for elem in elements:
            elem.select = True
            count += 1
    elif sel_range_val:
        start = int(sel_range_val[0])
        end = int(sel_range_val[1])
        for idx in range(start, min(end, len(elements))):
            elements[idx].select = True
            count += 1
    else:
        for idx in sel_indices:
            if 0 <= idx < len(elements):
                elements[idx].select = True
                count += 1

    bm.select_flush(True)
    return sel_type, count


def _run_operation(bm, obj, operation, params, selection):
    """Execute a single edit-mode operation. Returns (sel_type, selected_count)."""

    valid_operations = {
        "EXTRUDE", "INSET", "BEVEL", "SUBDIVIDE", "DISSOLVE", "MERGE",
        "LOOP_CUT", "SCALE", "TRANSLATE", "ROTATE",
        "EXTRUDE_ALONG_NORMALS", "BRIDGE", "FILL",
        "SPIN", "DELETE", "REMOVE_DOUBLES",
    }
    if operation not in valid_operations:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Invalid operation '{operation}'. Must be one of {sorted(valid_operations)}",
        )

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # LOOP_CUT is special — it doesn't use normal selection
    if operation == "LOOP_CUT":
        cuts = params.get("cuts", 1)
        edge_index = params.get("edge_index", 0)
        factor = params.get("factor", 0.0)

        if edge_index >= len(bm.edges):
            edge_index = 0

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.loopcut_slide(
            MESH_OT_loopcut={"number_cuts": cuts, "edge_index": edge_index},
            TRANSFORM_OT_edge_slide={"value": factor},
        )
        return "EDGE", cuts

    # Select geometry
    sel_type, count = _select_geometry(bm, selection)
    bmesh.update_edit_mesh(obj.data)

    if count == 0:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Selection matched 0 elements. Check your selection criteria. "
            f"Mesh has {len(bm.verts)} verts, {len(bm.edges)} edges, {len(bm.faces)} faces.",
        )

    if operation == "EXTRUDE":
        offset = params.get("offset", 1.0)
        direction = params.get("direction")
        move_vec = tuple(direction) if direction else (0, 0, offset)

        if sel_type == "FACE":
            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={"value": move_vec},
            )
        elif sel_type == "EDGE":
            bpy.ops.mesh.extrude_edges_move(
                TRANSFORM_OT_translate={"value": move_vec},
            )
        elif sel_type == "VERT":
            bpy.ops.mesh.extrude_vertices_move(
                TRANSFORM_OT_translate={"value": move_vec},
            )

    elif operation == "EXTRUDE_ALONG_NORMALS":
        offset = params.get("offset", 0.5)
        bpy.ops.mesh.extrude_region_move()
        bpy.ops.transform.shrink_fatten(value=-offset)

    elif operation == "INSET":
        thickness = params.get("thickness", 0.1)
        depth = params.get("depth", 0.0)
        bpy.ops.mesh.inset(thickness=thickness, depth=depth)

    elif operation == "BEVEL":
        width = params.get("width", 0.1)
        segments = params.get("segments", 1)
        if sel_type == "VERT":
            bpy.ops.mesh.bevel(offset=width, segments=segments, affect="VERTICES")
        else:
            bpy.ops.mesh.bevel(offset=width, segments=segments, affect="EDGES")

    elif operation == "SUBDIVIDE":
        cuts = params.get("cuts", 1)
        bpy.ops.mesh.subdivide(number_cuts=cuts)

    elif operation == "DISSOLVE":
        if sel_type == "VERT":
            bpy.ops.mesh.dissolve_verts()
        elif sel_type == "EDGE":
            bpy.ops.mesh.dissolve_edges()
        elif sel_type == "FACE":
            bpy.ops.mesh.dissolve_faces()

    elif operation == "MERGE":
        threshold = params.get("threshold", 0.0001)
        bpy.ops.mesh.merge(type="CENTER")
        bpy.ops.mesh.remove_doubles(threshold=threshold)

    elif operation == "SCALE":
        scale_vector = params.get("scale_vector", [1, 1, 1])
        bpy.ops.transform.resize(value=tuple(scale_vector))

    elif operation == "TRANSLATE":
        direction = params.get("direction", [0, 0, 0])
        bpy.ops.transform.translate(value=tuple(direction))

    elif operation == "ROTATE":
        angle = params.get("angle", 0.0)
        axis = params.get("axis", "Z").upper()
        constraint = {"X": (True, False, False), "Y": (False, True, False), "Z": (False, False, True)}
        bpy.ops.transform.rotate(
            value=angle,
            orient_axis=axis,
            constraint_axis=constraint.get(axis, (False, False, True)),
        )

    elif operation == "BRIDGE":
        bpy.ops.mesh.bridge_edge_loops()

    elif operation == "FILL":
        bpy.ops.mesh.fill()

    elif operation == "SPIN":
        # Spin/Lathe: revolve selected geometry around an axis
        # This is THE key operation for creating rotational objects
        # (lamp posts, vases, wheels, columns, etc.)
        # Use "segments" for spin step count (not "steps" which conflicts with chained ops)
        spin_segments = params.get("segments", 32)
        angle_val = params.get("angle", math.pi * 2)  # full 360 by default
        spin_axis = params.get("axis", "Z").upper()
        center = params.get("center", [0, 0, 0])

        axis_vec = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}

        bpy.ops.mesh.spin(
            steps=spin_segments,
            angle=angle_val,
            center=tuple(center),
            axis=axis_vec.get(spin_axis, (0, 0, 1)),
        )

    elif operation == "REMOVE_DOUBLES":
        # Just weld nearby verts (no merge to center) — use after SPIN to close seams
        threshold = params.get("threshold", 0.0001)
        bpy.ops.mesh.remove_doubles(threshold=threshold)

    elif operation == "DELETE":
        # Delete selected geometry
        delete_type = params.get("delete_type", "FACES")  # VERTS, EDGES, FACES, ONLY_FACE
        if delete_type == "VERTS":
            bpy.ops.mesh.delete(type="VERT")
        elif delete_type == "EDGES":
            bpy.ops.mesh.delete(type="EDGE")
        elif delete_type == "FACES":
            bpy.ops.mesh.delete(type="FACE")
        elif delete_type == "ONLY_FACE":
            bpy.ops.mesh.delete(type="ONLY_FACE")

    return sel_type, count


def handle_edit_geometry(params):
    """Edit mesh geometry using bmesh operations.

    Supports single operation or chained operations via the 'steps' parameter.

    Single operation params:
      object_name, operation, selection, + operation-specific params.

    Chained operations via 'steps' (all run in one edit-mode session):
      object_name: str
      steps: [
        {"operation": "EXTRUDE", "selection": {"type": "face", "position": "top"}, "direction": [0,0,0.5]},
        {"operation": "SCALE", "selection": {"type": "face", "position": "top"}, "scale_vector": [0.8,0.8,1]},
      ]

    Selection supports smart mode:
      {"type": "face", "position": "top"}     — topmost face(s)
      {"type": "face", "position": "bottom"}  — bottommost face(s)
      {"type": "face", "normal": [0,0,1]}     — faces pointing up
      {"type": "face", "z_greater": 0.5}      — faces above Z
      {"type": "vert", "z_range": [0.4,0.6]}  — verts in Z range
      {"type": "face", "indices": "all"}       — all faces
      {"type": "all"}                          — everything

    Operations: EXTRUDE, EXTRUDE_ALONG_NORMALS, INSET, BEVEL, SUBDIVIDE,
                DISSOLVE, MERGE, LOOP_CUT, SCALE, TRANSLATE, ROTATE,
                BRIDGE, FILL
    """
    if "object_name" not in params:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: object_name")

    object_name = params["object_name"]
    validate_object_name(object_name)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(ErrorCode.OBJECT_NOT_FOUND, f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, f"Object '{object_name}' is not a mesh (type: {obj.type})")

    # Ensure we're in object mode first, then switch to edit
    # Must set active object BEFORE trying to change mode
    bpy.context.view_layer.objects.active = obj
    if obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    bm = bmesh.from_edit_mesh(obj.data)

    # Check if we have chained steps or a single operation
    steps = params.get("steps")
    results = []

    if steps and isinstance(steps, list):
        # Chained operations — run each step in the same edit-mode session
        for i, step in enumerate(steps):
            op = step.get("operation", "").upper()
            sel = step.get("selection", {"type": "face", "position": "top"})

            # Refresh bmesh lookup tables between operations
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            try:
                sel_type, count = _run_operation(bm, obj, op, step, sel)
                results.append({"step": i, "operation": op, "selected": count, "success": True})
            except Exception as e:
                results.append({"step": i, "operation": op, "error": str(e), "success": False})
                break

    else:
        # Single operation (backwards compatible)
        operation = params.get("operation", "").upper()
        selection = params.get("selection", {"type": "all"})

        if not operation:
            bpy.ops.object.mode_set(mode="OBJECT")
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: operation")

        sel_type, count = _run_operation(bm, obj, operation, params, selection)
        results.append({"step": 0, "operation": operation, "selected": count, "success": True})

    # Return to object mode
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh = obj.data
    return {
        "success": all(r["success"] for r in results),
        "steps": results,
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "face_count": len(mesh.polygons),
    }


# ---------------------------------------------------------------------------
# 4. mesh.get_geometry
# ---------------------------------------------------------------------------

def handle_get_geometry(params):
    """Read mesh geometry data from an object."""
    if not params.get("object_name"):
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: object_name")

    object_name = params["object_name"]
    include_normals = params.get("include_normals", False)
    include_uvs = params.get("include_uvs", False)

    validate_object_name(object_name)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{object_name}' not found",
        )
    if obj.type != "MESH":
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Object '{object_name}' is not a mesh (type: {obj.type})",
        )

    mesh = obj.data
    mesh.calc_loop_triangles()

    vertices = [[v.co.x, v.co.y, v.co.z] for v in mesh.vertices]
    faces = [[v for v in p.vertices] for p in mesh.polygons]
    edges = [[e.vertices[0], e.vertices[1]] for e in mesh.edges]

    result = {
        "vertices": vertices,
        "faces": faces,
        "edges": edges,
        "vertex_count": len(mesh.vertices),
        "face_count": len(mesh.polygons),
        "edge_count": len(mesh.edges),
    }

    if include_normals:
        mesh.calc_normals()
        normals = [[v.normal.x, v.normal.y, v.normal.z] for v in mesh.vertices]
        result["normals"] = normals

    if include_uvs:
        uvs = []
        if mesh.uv_layers.active:
            uv_layer = mesh.uv_layers.active.data
            uvs = [[uv.uv.x, uv.uv.y] for uv in uv_layer]
        result["uvs"] = uvs

    return result


# ---------------------------------------------------------------------------
# 5. mesh.set_smooth_shading
# ---------------------------------------------------------------------------

def handle_set_smooth_shading(params):
    """Set smooth or flat shading on a mesh object."""
    for req in ("object_name",):
        if not params.get(req):
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, f"Missing required parameter: {req}")

    object_name = params["object_name"]
    smooth = params["smooth"]
    auto_smooth_angle = params.get("auto_smooth_angle", 30.0)

    validate_object_name(object_name)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{object_name}' not found",
        )
    if obj.type != "MESH":
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Object '{object_name}' is not a mesh (type: {obj.type})",
        )

    mesh = obj.data

    # Set smooth/flat shading on all faces
    for polygon in mesh.polygons:
        polygon.use_smooth = smooth

    # Set auto smooth angle (attribute removed in Blender 4.1+)
    if hasattr(mesh, "use_auto_smooth"):
        if smooth:
            mesh.use_auto_smooth = True
            mesh.auto_smooth_angle = math.radians(auto_smooth_angle)
        else:
            mesh.use_auto_smooth = False

    mesh.update()

    return {
        "object_name": obj.name,
        "smooth": smooth,
        "auto_smooth_angle": auto_smooth_angle,
    }


# ---------------------------------------------------------------------------
# 6. mesh.separate
# ---------------------------------------------------------------------------

def handle_separate(params):
    """Separate a mesh into multiple objects."""
    for req in ("object_name", "method"):
        if not params.get(req):
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, f"Missing required parameter: {req}")

    object_name = params["object_name"]
    method = params["method"].upper()

    validate_object_name(object_name)

    valid_methods = {"BY_MATERIAL", "BY_LOOSE_PARTS"}
    if method not in valid_methods:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Invalid method '{method}'. Must be one of {sorted(valid_methods)}",
        )

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{object_name}' not found",
        )
    if obj.type != "MESH":
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Object '{object_name}' is not a mesh (type: {obj.type})",
        )

    # Track existing objects before separation
    existing_names = set(o.name for o in bpy.data.objects)

    # Select only the target object
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Enter edit mode, select all, then separate
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")

    if method == "BY_MATERIAL":
        bpy.ops.mesh.separate(type="MATERIAL")
    elif method == "BY_LOOSE_PARTS":
        bpy.ops.mesh.separate(type="LOOSE")

    bpy.ops.object.mode_set(mode="OBJECT")

    # Find newly created objects
    new_names = [o.name for o in bpy.data.objects if o.name not in existing_names]

    return {
        "original": obj.name,
        "new_objects": new_names,
    }


# ---------------------------------------------------------------------------
# 7. mesh.join
# ---------------------------------------------------------------------------

def handle_join(params):
    """Join multiple mesh objects into one."""
    if "object_names" not in params:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: object_names")

    object_names = params["object_names"]
    if not object_names or len(object_names) < 2:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "At least two object names are required for joining",
        )

    objects = []
    for name in object_names:
        validate_object_name(name)
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Object '{name}' not found",
            )
        if obj.type != "MESH":
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                f"Object '{name}' is not a mesh (type: {obj.type})",
            )
        objects.append(obj)

    # Deselect all, then select target objects
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)

    # Set the first object as active (it will be the result)
    bpy.context.view_layer.objects.active = objects[0]

    bpy.ops.object.join()

    result_obj = bpy.context.active_object
    mesh = result_obj.data

    return {
        "result_name": result_obj.name,
        "vertex_count": len(mesh.vertices),
        "face_count": len(mesh.polygons),
    }


# ---------------------------------------------------------------------------
# 8. mesh.set_origin
# ---------------------------------------------------------------------------

def handle_set_origin(params):
    """Set the origin point of a mesh object."""
    for req in ("object_name", "origin_type"):
        if not params.get(req):
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, f"Missing required parameter: {req}")

    object_name = params["object_name"]
    origin_type = params["origin_type"].upper()

    validate_object_name(object_name)

    valid_origin_types = {
        "ORIGIN_GEOMETRY",
        "ORIGIN_CENTER_OF_MASS",
        "ORIGIN_CENTER_OF_VOLUME",
        "ORIGIN_CURSOR",
        "GEOMETRY_ORIGIN",
    }
    if origin_type not in valid_origin_types:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Invalid origin type '{origin_type}'. Must be one of {sorted(valid_origin_types)}",
        )

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{object_name}' not found",
        )

    # Select only the target object
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Map to bpy.ops center type parameter where needed
    if origin_type == "ORIGIN_CENTER_OF_MASS":
        bpy.ops.object.origin_set(
            type="ORIGIN_CENTER_OF_MASS", center="MEDIAN",
        )
    elif origin_type == "ORIGIN_CENTER_OF_VOLUME":
        bpy.ops.object.origin_set(
            type="ORIGIN_CENTER_OF_VOLUME", center="MEDIAN",
        )
    else:
        bpy.ops.object.origin_set(type=origin_type)

    return {
        "object_name": obj.name,
        "origin_type": origin_type,
        "location": list(obj.location),
    }


# ---------------------------------------------------------------------------
# 9. mesh.analyze_profile
# ---------------------------------------------------------------------------

def handle_analyze_profile(params):
    """Deep analysis of a mesh object for reverse-engineering construction recipes.

    Returns bounding box, Z-slice profiles, material zones, face normal distribution,
    loose parts count, symmetry detection, and section identification.
    """
    from mathutils import Vector

    if not params.get("object_name"):
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: object_name")

    object_name = params["object_name"]
    num_slices = params.get("num_slices", 20)
    validate_object_name(object_name)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(ErrorCode.OBJECT_NOT_FOUND, f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, f"Object '{object_name}' is not a mesh")

    mesh = obj.data
    # calc_normals() removed in Blender 4.1+; normals auto-calculated

    # Transform vertices to world space
    matrix = obj.matrix_world
    world_verts = [matrix @ v.co for v in mesh.vertices]

    if not world_verts:
        return {"error": "Mesh has no vertices"}

    # --- Bounding box ---
    xs = [v.x for v in world_verts]
    ys = [v.y for v in world_verts]
    zs = [v.z for v in world_verts]
    bbox = {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
        "center": [(min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2],
        "dimensions": [max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)],
    }

    # --- Z-slice profiles ---
    z_min, z_max = min(zs), max(zs)
    z_range = z_max - z_min
    slices = []
    if z_range > 0:
        for i in range(num_slices + 1):
            z = z_min + (z_range * i / num_slices)
            tolerance = z_range / (num_slices * 2)

            # Find vertices near this Z height
            nearby = [v for v in world_verts if abs(v.z - z) < tolerance]
            if nearby:
                slice_xs = [v.x for v in nearby]
                slice_ys = [v.y for v in nearby]
                cx = (min(slice_xs) + max(slice_xs)) / 2
                cy = (min(slice_ys) + max(slice_ys)) / 2
                # Radius from center of bounding box
                center_x = bbox["center"][0]
                center_y = bbox["center"][1]
                radii = [math.sqrt((v.x - center_x)**2 + (v.y - center_y)**2) for v in nearby]
                slices.append({
                    "z": round(z, 4),
                    "z_normalized": round(i / num_slices, 3),
                    "vertex_count": len(nearby),
                    "radius_min": round(min(radii), 4),
                    "radius_max": round(max(radii), 4),
                    "radius_avg": round(sum(radii) / len(radii), 4),
                    "width_x": round(max(slice_xs) - min(slice_xs), 4),
                    "width_y": round(max(slice_ys) - min(slice_ys), 4),
                    "center": [round(cx, 4), round(cy, 4)],
                })
            else:
                slices.append({
                    "z": round(z, 4),
                    "z_normalized": round(i / num_slices, 3),
                    "vertex_count": 0,
                })

    # --- Material zones ---
    material_zones = []
    for i, mat_slot in enumerate(obj.material_slots):
        mat_name = mat_slot.material.name if mat_slot.material else f"slot_{i}_empty"
        # Find faces using this material
        mat_faces = [p for p in mesh.polygons if p.material_index == i]
        if mat_faces:
            face_zs = []
            for f in mat_faces:
                fz = sum(world_verts[vi].z for vi in f.vertices) / len(f.vertices)
                face_zs.append(fz)
            # Get material color if available
            color = None
            if mat_slot.material and mat_slot.material.use_nodes:
                for node in mat_slot.material.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        inp = node.inputs.get("Base Color")
                        if inp and hasattr(inp, "default_value"):
                            color = [round(c, 3) for c in inp.default_value[:3]]
                        break
            zone = {
                "material_name": mat_name,
                "face_count": len(mat_faces),
                "z_min": round(min(face_zs), 4),
                "z_max": round(max(face_zs), 4),
                "z_avg": round(sum(face_zs) / len(face_zs), 4),
            }
            if color:
                zone["base_color_rgb"] = color
            material_zones.append(zone)

    # --- Face normal distribution ---
    normal_bins = {"up": 0, "down": 0, "north": 0, "south": 0, "east": 0, "west": 0, "other": 0}
    for poly in mesh.polygons:
        # Transform normal to world space (rotation only)
        wn = (matrix.to_3x3() @ Vector(poly.normal)).normalized()
        # Classify by dominant axis
        abs_x, abs_y, abs_z = abs(wn.x), abs(wn.y), abs(wn.z)
        if abs_z >= abs_x and abs_z >= abs_y:
            if wn.z > 0.5:
                normal_bins["up"] += 1
            elif wn.z < -0.5:
                normal_bins["down"] += 1
            else:
                normal_bins["other"] += 1
        elif abs_y >= abs_x:
            if wn.y > 0.5:
                normal_bins["north"] += 1  # +Y
            elif wn.y < -0.5:
                normal_bins["south"] += 1  # -Y
            else:
                normal_bins["other"] += 1
        else:
            if wn.x > 0.5:
                normal_bins["east"] += 1   # +X
            elif wn.x < -0.5:
                normal_bins["west"] += 1   # -X
            else:
                normal_bins["other"] += 1

    # --- Loose parts detection (using bmesh) ---
    bm = bmesh.new()
    bm.from_mesh(mesh)
    loose_parts = 0
    visited = set()
    for v in bm.verts:
        if v.index not in visited:
            loose_parts += 1
            # BFS to find connected component
            stack = [v]
            while stack:
                current = stack.pop()
                if current.index in visited:
                    continue
                visited.add(current.index)
                for edge in current.link_edges:
                    other = edge.other_vert(current)
                    if other.index not in visited:
                        stack.append(other)
    bm.free()

    # --- Symmetry detection ---
    symmetry = {"x_symmetric": False, "y_symmetric": False}
    # Check X symmetry: for each vertex at +X, is there one at -X?
    tolerance_sym = z_range * 0.01 if z_range > 0 else 0.01
    center_x = bbox["center"][0]
    center_y = bbox["center"][1]

    # Sample up to 200 vertices for speed
    sample_verts = world_verts[:200] if len(world_verts) > 200 else world_verts
    x_match_count = 0
    y_match_count = 0
    for v in sample_verts:
        # Check X mirror
        mirror_x = Vector((2 * center_x - v.x, v.y, v.z))
        for v2 in sample_verts:
            if (mirror_x - v2).length < tolerance_sym:
                x_match_count += 1
                break
        # Check Y mirror
        mirror_y = Vector((v.x, 2 * center_y - v.y, v.z))
        for v2 in sample_verts:
            if (mirror_y - v2).length < tolerance_sym:
                y_match_count += 1
                break

    total_sampled = len(sample_verts)
    if total_sampled > 0:
        symmetry["x_symmetric"] = (x_match_count / total_sampled) > 0.85
        symmetry["y_symmetric"] = (y_match_count / total_sampled) > 0.85
        symmetry["x_match_ratio"] = round(x_match_count / total_sampled, 3)
        symmetry["y_match_ratio"] = round(y_match_count / total_sampled, 3)

    # --- Section identification (detect distinct sections by vertex density along Z) ---
    sections = []
    if z_range > 0 and slices:
        # Find sections by looking for gaps or radius changes in Z-slices
        prev_radius = None
        section_start = 0
        section_radii = []
        for i, s in enumerate(slices):
            if s["vertex_count"] == 0:
                if section_radii:
                    sections.append({
                        "z_start": round(slices[section_start]["z"], 4),
                        "z_end": round(slices[i-1]["z"], 4),
                        "avg_radius": round(sum(section_radii) / len(section_radii), 4),
                        "min_radius": round(min(section_radii), 4),
                        "max_radius": round(max(section_radii), 4),
                        "slice_count": len(section_radii),
                    })
                    section_radii = []
                section_start = i + 1
            else:
                r = s["radius_avg"]
                if prev_radius is not None and section_radii:
                    # Detect significant radius change (>50% change = new section)
                    if prev_radius > 0 and abs(r - prev_radius) / prev_radius > 0.5:
                        sections.append({
                            "z_start": round(slices[section_start]["z"], 4),
                            "z_end": round(slices[i-1]["z"], 4),
                            "avg_radius": round(sum(section_radii) / len(section_radii), 4),
                            "min_radius": round(min(section_radii), 4),
                            "max_radius": round(max(section_radii), 4),
                            "slice_count": len(section_radii),
                        })
                        section_radii = []
                        section_start = i
                section_radii.append(r)
                prev_radius = r

        # Final section
        if section_radii:
            sections.append({
                "z_start": round(slices[section_start]["z"], 4),
                "z_end": round(slices[-1]["z"], 4) if slices[-1]["vertex_count"] > 0 else round(slices[section_start + len(section_radii) - 1]["z"], 4),
                "avg_radius": round(sum(section_radii) / len(section_radii), 4),
                "min_radius": round(min(section_radii), 4),
                "max_radius": round(max(section_radii), 4),
                "slice_count": len(section_radii),
            })

    # --- Modifier info ---
    modifiers = [{"name": mod.name, "type": mod.type} for mod in obj.modifiers]

    return {
        "object_name": obj.name,
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "face_count": len(mesh.polygons),
        "bounding_box": bbox,
        "z_slices": slices,
        "material_zones": material_zones,
        "face_normal_distribution": normal_bins,
        "loose_parts": loose_parts,
        "symmetry": symmetry,
        "sections": sections,
        "modifiers": modifiers,
        "has_uvs": len(mesh.uv_layers) > 0,
        "uv_layer_count": len(mesh.uv_layers),
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    """Register all mesh tool handlers with the dispatcher."""
    register_handler("mesh.create_primitive", handle_create_primitive)
    register_handler("mesh.create_custom", handle_create_custom)
    register_handler("mesh.edit_geometry", handle_edit_geometry)
    register_handler("mesh.get_geometry", handle_get_geometry)
    register_handler("mesh.set_smooth_shading", handle_set_smooth_shading)
    register_handler("mesh.separate", handle_separate)
    register_handler("mesh.join", handle_join)
    register_handler("mesh.set_origin", handle_set_origin)
    register_handler("mesh.analyze_profile", handle_analyze_profile)
