"""Object manipulation handler module for BlenderMCP.

Provides tools for transforming, duplicating, deleting, parenting,
and managing Blender objects via MCP.
"""

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None
    mathutils = None

try:
    from ..dispatcher import register_handler
    from ..validation import validate_object_name, validate_vector3
    from ..shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from addon.dispatcher import register_handler
    from addon.validation import validate_object_name, validate_vector3
    from shared.error_codes import ErrorCode, BlenderMCPError


def _get_object(name):
    """Retrieve a Blender object by name, raising an error if not found."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{name}' not found"
        )
    return obj


def _vector_to_list(vec):
    """Convert a Blender Vector or Euler to a plain list of floats."""
    return [round(v, 6) for v in vec]


def _matrix_to_list(matrix):
    """Convert a 4x4 Matrix to a nested list."""
    return [[round(cell, 6) for cell in row] for row in matrix]


# ---------------------------------------------------------------------------
# 1. object.set_transform
# ---------------------------------------------------------------------------

def handle_set_transform(params):
    """Set the world transform of an object.

    Params:
        name (str): Object name.
        location (list[float], optional): [x, y, z] world location.
        rotation (list[float], optional): [x, y, z] euler rotation in radians.
        scale (list[float], optional): [x, y, z] scale.

    Returns:
        dict with name, location, rotation, scale.
    """
    name = validate_object_name(params.get("name"))
    obj = _get_object(name)

    if "location" in params and params["location"] is not None:
        loc = validate_vector3(params["location"], "location")
        obj.location = mathutils.Vector(loc)

    if "rotation" in params and params["rotation"] is not None:
        rot = validate_vector3(params["rotation"], "rotation")
        obj.rotation_euler = mathutils.Euler(rot, 'XYZ')

    if "scale" in params and params["scale"] is not None:
        sc = validate_vector3(params["scale"], "scale")
        obj.scale = mathutils.Vector(sc)

    # Force depsgraph update
    bpy.context.view_layer.update()

    return {
        "name": obj.name,
        "location": _vector_to_list(obj.location),
        "rotation": _vector_to_list(obj.rotation_euler),
        "scale": _vector_to_list(obj.scale),
    }


# ---------------------------------------------------------------------------
# 2. object.get_transform
# ---------------------------------------------------------------------------

def handle_get_transform(params):
    """Get the transform of an object in the specified space.

    Params:
        name (str): Object name.
        space (str, optional): 'WORLD' or 'LOCAL'. Defaults to 'WORLD'.

    Returns:
        dict with name, space, location, rotation, scale, matrix_world.
    """
    name = validate_object_name(params.get("name"))
    obj = _get_object(name)

    space = params.get("space", "WORLD").upper()
    if space not in ("WORLD", "LOCAL"):
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Invalid space '{space}'. Must be 'WORLD' or 'LOCAL'."
        )

    if space == "WORLD":
        location = _vector_to_list(obj.matrix_world.to_translation())
        rotation = _vector_to_list(obj.matrix_world.to_euler('XYZ'))
        scale = _vector_to_list(obj.matrix_world.to_scale())
    else:
        location = _vector_to_list(obj.location)
        rotation = _vector_to_list(obj.rotation_euler)
        scale = _vector_to_list(obj.scale)

    return {
        "name": obj.name,
        "space": space,
        "location": location,
        "rotation": rotation,
        "scale": scale,
        "matrix_world": _matrix_to_list(obj.matrix_world),
    }


# ---------------------------------------------------------------------------
# 3. object.duplicate
# ---------------------------------------------------------------------------

def handle_duplicate(params):
    """Duplicate an object.

    Params:
        name (str): Source object name.
        linked (bool, optional): If True, share data with original. Default False.
        new_name (str, optional): Name for the duplicate.
        offset (list[float], optional): [x, y, z] positional offset for duplicate.

    Returns:
        dict with original, duplicate, location.
    """
    name = validate_object_name(params.get("name"))
    obj = _get_object(name)
    linked = params.get("linked", False)

    new_obj = obj.copy()

    if not linked and obj.data is not None:
        new_obj.data = obj.data.copy()

    if "new_name" in params and params["new_name"]:
        new_obj.name = params["new_name"]

    if "offset" in params and params["offset"] is not None:
        offset = validate_vector3(params["offset"], "offset")
        new_obj.location = mathutils.Vector(obj.location) + mathutils.Vector(offset)

    # Link duplicate to the same collections as the original
    linked_to_any = False
    for collection in bpy.data.collections:
        if obj.name in collection.objects:
            collection.objects.link(new_obj)
            linked_to_any = True

    # If the object was only in the scene collection, link there
    if not linked_to_any:
        bpy.context.scene.collection.objects.link(new_obj)

    bpy.context.view_layer.update()

    return {
        "original": obj.name,
        "duplicate": new_obj.name,
        "location": _vector_to_list(new_obj.location),
    }


# ---------------------------------------------------------------------------
# 4. object.delete
# ---------------------------------------------------------------------------

def _collect_children_recursive(obj):
    """Recursively collect all children of an object."""
    children = []
    for child in obj.children:
        children.append(child)
        children.extend(_collect_children_recursive(child))
    return children


def handle_delete(params):
    """Delete one or more objects.

    Params:
        names (list[str]): List of object names to delete.
        delete_children (bool, optional): If True, recursively delete children. Default False.

    Returns:
        dict with deleted (list of names) and count.
    """
    names = params.get("names")
    if not names or not isinstance(names, list):
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Parameter 'names' must be a non-empty list of strings."
        )

    delete_children = params.get("delete_children", False)
    deleted = []

    # Gather all objects to delete first to avoid mutation during iteration
    objects_to_delete = []
    for obj_name in names:
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            raise BlenderMCPError(
                ErrorCode.OBJECT_NOT_FOUND,
                f"Object '{obj_name}' not found"
            )
        objects_to_delete.append(obj)
        if delete_children:
            objects_to_delete.extend(_collect_children_recursive(obj))

    # Deduplicate while preserving order
    seen = set()
    unique_objects = []
    for obj in objects_to_delete:
        if obj.name not in seen:
            seen.add(obj.name)
            unique_objects.append(obj)

    for obj in unique_objects:
        deleted.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)

    return {
        "deleted": deleted,
        "count": len(deleted),
    }


# ---------------------------------------------------------------------------
# 5. object.parent
# ---------------------------------------------------------------------------

def handle_parent(params):
    """Set an object's parent.

    Params:
        child (str): Name of the child object.
        parent (str): Name of the parent object.
        keep_transform (bool, optional): Preserve world position. Default True.

    Returns:
        dict with child, parent.
    """
    child_name = validate_object_name(params.get("child"))
    parent_name = validate_object_name(params.get("parent"))
    keep_transform = params.get("keep_transform", True)

    child_obj = _get_object(child_name)
    parent_obj = _get_object(parent_name)

    if keep_transform:
        child_obj.parent = parent_obj
        child_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
    else:
        child_obj.parent = parent_obj

    bpy.context.view_layer.update()

    return {
        "child": child_obj.name,
        "parent": parent_obj.name,
    }


# ---------------------------------------------------------------------------
# 6. object.unparent
# ---------------------------------------------------------------------------

def handle_unparent(params):
    """Clear an object's parent.

    Params:
        child (str): Name of the child object.
        keep_transform (bool, optional): Preserve world position. Default True.

    Returns:
        dict with child, previous_parent.
    """
    child_name = validate_object_name(params.get("child"))
    keep_transform = params.get("keep_transform", True)

    child_obj = _get_object(child_name)

    previous_parent = child_obj.parent.name if child_obj.parent else None

    if keep_transform:
        # Store world matrix before clearing parent
        world_matrix = child_obj.matrix_world.copy()
        child_obj.parent = None
        child_obj.matrix_world = world_matrix
    else:
        child_obj.parent = None

    bpy.context.view_layer.update()

    return {
        "child": child_obj.name,
        "previous_parent": previous_parent,
    }


# ---------------------------------------------------------------------------
# 7. object.move_to_collection
# ---------------------------------------------------------------------------

def handle_move_to_collection(params):
    """Move an object to a specified collection.

    Unlinks the object from all current collections and links it
    to the target collection, creating the collection if it does not exist.

    Params:
        name (str): Object name.
        collection (str): Target collection name.

    Returns:
        dict with name, collection.
    """
    obj_name = validate_object_name(params.get("name"))
    collection_name = params.get("collection")
    if not collection_name or not isinstance(collection_name, str):
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Parameter 'collection' must be a non-empty string."
        )

    obj = _get_object(obj_name)

    # Get or create target collection
    target_col = bpy.data.collections.get(collection_name)
    if target_col is None:
        target_col = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(target_col)

    # Unlink from all current collections (including scene collection)
    for col in list(obj.users_collection):
        col.objects.unlink(obj)

    # Link to target collection
    target_col.objects.link(obj)

    bpy.context.view_layer.update()

    return {
        "name": obj.name,
        "collection": target_col.name,
    }


# ---------------------------------------------------------------------------
# 8. object.apply_transform
# ---------------------------------------------------------------------------

def handle_apply_transform(params):
    """Apply (freeze) the object's transforms.

    This bakes the current location/rotation/scale into the mesh data
    and resets the transform channels. Critical for UE5 export workflows.

    Params:
        name (str): Object name.
        location (bool, optional): Apply location. Default True.
        rotation (bool, optional): Apply rotation. Default True.
        scale (bool, optional): Apply scale. Default True.

    Returns:
        dict with name, applied (dict of location, rotation, scale bools).
    """
    obj_name = validate_object_name(params.get("name"))
    obj = _get_object(obj_name)

    apply_location = params.get("location", True)
    apply_rotation = params.get("rotation", True)
    apply_scale = params.get("scale", True)

    # Deselect all, then select and activate the target object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.transform_apply(
        location=apply_location,
        rotation=apply_rotation,
        scale=apply_scale,
    )

    bpy.context.view_layer.update()

    return {
        "name": obj.name,
        "applied": {
            "location": apply_location,
            "rotation": apply_rotation,
            "scale": apply_scale,
        },
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    """Register all object manipulation handlers with the dispatcher."""
    register_handler("object.set_transform", handle_set_transform)
    register_handler("object.get_transform", handle_get_transform)
    register_handler("object.duplicate", handle_duplicate)
    register_handler("object.delete", handle_delete)
    register_handler("object.parent", handle_parent)
    register_handler("object.unparent", handle_unparent)
    register_handler("object.move_to_collection", handle_move_to_collection)
    register_handler("object.apply_transform", handle_apply_transform)
