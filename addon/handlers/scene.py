"""Scene management handlers for BlenderMCP addon."""

import fnmatch

try:
    import bpy
except ImportError:
    bpy = None

try:
    from ..dispatcher import register_handler
    from ..validation import validate_params, validate_object_name
    from ..shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from addon.dispatcher import register_handler
    from addon.validation import validate_params, validate_object_name
    from shared.error_codes import ErrorCode, BlenderMCPError


def _ensure_bpy():
    """Raise an error if bpy is not available."""
    if bpy is None:
        raise BlenderMCPError(
            ErrorCode.INTERNAL_ERROR,
            "bpy module is not available outside of Blender"
        )


def handle_get_info(params: dict) -> dict:
    """Return general scene information."""
    _ensure_bpy()
    scene = bpy.context.scene
    unit = scene.unit_settings

    return {
        "name": scene.name,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "fps": scene.render.fps,
        "unit_system": unit.system,
        "unit_scale": unit.scale_length,
        "length_unit": unit.length_unit,
        "object_count": len(scene.objects),
        "render_engine": scene.render.engine,
    }


def handle_list_objects(params: dict) -> dict:
    """List objects in the scene with optional filters."""
    _ensure_bpy()
    scene = bpy.context.scene

    type_filter = params.get("type_filter")
    name_pattern = params.get("name_pattern")
    collection_name = params.get("collection")

    # Determine source of objects
    if collection_name:
        col = bpy.data.collections.get(collection_name)
        if col is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Collection '{collection_name}' not found"
            )
        objects = col.objects
    else:
        objects = scene.objects

    result = []
    for obj in objects:
        # Apply type filter
        if type_filter and obj.type != type_filter:
            continue

        # Apply name pattern filter
        if name_pattern and not fnmatch.fnmatch(obj.name, name_pattern):
            continue

        result.append({
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "visible": obj.visible_get(),
        })

    return {"objects": result}


def handle_get_object(params: dict) -> dict:
    """Return detailed information about a specific object."""
    _ensure_bpy()
    name = params.get("name")
    if not name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: name")
    validate_object_name(name)

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{name}' not found"
        )

    result = {
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation_euler": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "dimensions": list(obj.dimensions),
        "materials": [str(slot.material.name) if slot.material else None for slot in obj.material_slots],
        "modifiers": [{"name": mod.name, "type": mod.type} for mod in obj.modifiers],
        "parent": obj.parent.name if obj.parent else None,
        "children": [child.name for child in obj.children],
        "visible": obj.visible_get(),
        "selected": obj.select_get(),
    }

    # Add mesh-specific stats
    if obj.type == 'MESH' and obj.data:
        mesh = obj.data
        result["mesh_stats"] = {
            "vertex_count": len(mesh.vertices),
            "edge_count": len(mesh.edges),
            "face_count": len(mesh.polygons),
            "has_uvs": len(mesh.uv_layers) > 0,
            "material_count": len(mesh.materials),
        }

    return result


def _build_hierarchy(obj):
    """Recursively build a hierarchy dict from an object."""
    return {
        "name": obj.name,
        "type": obj.type,
        "children": [_build_hierarchy(child) for child in obj.children],
    }


def handle_get_hierarchy(params: dict) -> dict:
    """Return the parent-child hierarchy tree."""
    _ensure_bpy()

    root_name = params.get("root")

    if root_name:
        root_obj = bpy.data.objects.get(root_name)
        if root_obj is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Object '{root_name}' not found"
            )
        hierarchy = [_build_hierarchy(root_obj)]
    else:
        # Find all root objects (no parent)
        roots = [obj for obj in bpy.context.scene.objects if obj.parent is None]
        hierarchy = [_build_hierarchy(obj) for obj in roots]

    return {"hierarchy": hierarchy}


def handle_set_unit_system(params: dict) -> dict:
    """Set the scene unit system, scale, and/or length unit."""
    _ensure_bpy()

    unit = bpy.context.scene.unit_settings
    changed = {}

    system = params.get("system")
    if system is not None:
        valid_systems = ("METRIC", "IMPERIAL", "NONE")
        if system not in valid_systems:
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                f"Invalid unit system '{system}'. Must be one of: {', '.join(valid_systems)}"
            )
        unit.system = system
        changed["system"] = system

    scale = params.get("scale")
    if scale is not None:
        if not isinstance(scale, (int, float)) or scale <= 0:
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                "Scale must be a positive number"
            )
        unit.scale_length = float(scale)
        changed["scale"] = float(scale)

    length_unit = params.get("length_unit")
    if length_unit is not None:
        valid_units = (
            "METERS", "CENTIMETERS", "MILLIMETERS", "KILOMETERS",
            "FEET", "INCHES", "MILES", "ADAPTIVE", "MICROMETERS",
        )
        if length_unit not in valid_units:
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                f"Invalid length unit '{length_unit}'. Must be one of: {', '.join(valid_units)}"
            )
        unit.length_unit = length_unit
        changed["length_unit"] = length_unit

    if not changed:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "No unit parameters provided. Supply at least one of: system, scale, length_unit"
        )

    return {"changed": changed}


def handle_manage_collection(params: dict) -> dict:
    """Create, delete, rename, or move a collection."""
    _ensure_bpy()
    action = params.get("action")
    name = params.get("name")
    if not action:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: action")
    if not name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: name")
    action = action.upper()

    if action == "CREATE":
        if bpy.data.collections.get(name):
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                f"Collection '{name}' already exists"
            )
        new_col = bpy.data.collections.new(name)

        parent_name = params.get("parent")
        if parent_name:
            parent_col = bpy.data.collections.get(parent_name)
            if parent_col is None:
                raise BlenderMCPError(
                    ErrorCode.OBJECT_NOT_FOUND,
                    f"Parent collection '{parent_name}' not found"
                )
            parent_col.children.link(new_col)
        else:
            bpy.context.scene.collection.children.link(new_col)

        return {"action": "CREATE", "name": name}

    elif action == "DELETE":
        col = bpy.data.collections.get(name)
        if col is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Collection '{name}' not found"
            )
        bpy.data.collections.remove(col)
        return {"action": "DELETE", "name": name}

    elif action == "RENAME":
        new_name = params.get("new_name")
        if not new_name:
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                "new_name is required for RENAME action"
            )
        col = bpy.data.collections.get(name)
        if col is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Collection '{name}' not found"
            )
        col.name = new_name
        return {"action": "RENAME", "old_name": name, "new_name": col.name}

    elif action == "MOVE":
        parent_name = params.get("parent")
        if not parent_name:
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                "parent is required for MOVE action"
            )
        col = bpy.data.collections.get(name)
        if col is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Collection '{name}' not found"
            )
        target_parent = bpy.data.collections.get(parent_name)
        if target_parent is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Target parent collection '{parent_name}' not found"
            )

        # Unlink from all current parents
        for other_col in bpy.data.collections:
            if col.name in other_col.children:
                other_col.children.unlink(col)
        # Also unlink from scene collection if linked there
        scene_col = bpy.context.scene.collection
        if col.name in scene_col.children:
            scene_col.children.unlink(col)

        # Link to new parent
        target_parent.children.link(col)
        return {"action": "MOVE", "name": name, "parent": parent_name}

    else:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Invalid action '{action}'. Must be one of: CREATE, DELETE, RENAME, MOVE"
        )


def handle_set_active_object(params: dict) -> dict:
    """Set the active object and select it."""
    _ensure_bpy()
    name = params.get("name")
    if not name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: name")
    validate_object_name(name)

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{name}' not found"
        )

    # Deselect all first
    bpy.ops.object.select_all(action='DESELECT')

    # Select and make active
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    return {"name": obj.name, "active": True, "selected": True}


def register():
    """Register all scene management handlers."""
    register_handler("scene.get_info", handle_get_info)
    register_handler("scene.list_objects", handle_list_objects)
    register_handler("scene.get_object", handle_get_object)
    register_handler("scene.get_hierarchy", handle_get_hierarchy)
    register_handler("scene.set_unit_system", handle_set_unit_system)
    register_handler("scene.manage_collection", handle_manage_collection)
    register_handler("scene.set_active_object", handle_set_active_object)
