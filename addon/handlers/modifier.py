"""Blender addon handler for modifier tools."""

try:
    import bpy
except ImportError:
    bpy = None

try:
    from ..dispatcher import register_handler
    from ..validation import validate_object_name
    from ..shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from addon.dispatcher import register_handler
    from addon.validation import validate_object_name
    from shared.error_codes import ErrorCode, BlenderMCPError


VALID_MODIFIER_TYPES = {
    "SUBSURF", "MIRROR", "ARRAY", "BEVEL", "SOLIDIFY", "DECIMATE", "REMESH",
    "BOOLEAN", "SHRINKWRAP", "SMOOTH", "WEIGHTED_NORMAL", "TRIANGULATE",
    "WIREFRAME", "EDGE_SPLIT", "SCREW", "SKIN", "MULTIRES", "SIMPLE_DEFORM",
    "CAST", "LATTICE", "CURVE", "ARMATURE", "SURFACE_DEFORM", "MESH_DEFORM",
    "DATA_TRANSFER", "NORMAL_EDIT", "UV_WARP", "UV_PROJECT",
    "VERTEX_WEIGHT_EDIT", "VERTEX_WEIGHT_MIX", "VERTEX_WEIGHT_PROXIMITY",
    "WELD", "CORRECTIVE_SMOOTH", "LAPLACIANSMOOTH",
}


def _set_modifier_properties(modifier, properties):
    """Set properties on a modifier, returning the list of properties that were actually set."""
    properties_set = []
    if not properties:
        return properties_set

    for key, value in properties.items():
        if not hasattr(modifier, key):
            continue

        try:
            # For list values, try direct assignment (handles Vector, array, etc.)
            if isinstance(value, list):
                setattr(modifier, key, value)
            elif isinstance(value, (int, float, bool, str)):
                setattr(modifier, key, value)
            else:
                setattr(modifier, key, value)
            properties_set.append(key)
        except (TypeError, AttributeError, ValueError):
            # Skip properties that can't be set
            pass

    return properties_set


def handle_modifier_add(params):
    """Add a modifier to an object.

    params:
        object_name (str): Name of the target object.
        type (str): Modifier type (e.g. SUBSURF, MIRROR, ARRAY, ...).
        name (str, optional): Custom name for the modifier.
        properties (dict, optional): Modifier-specific properties to set.
    """
    object_name = params.get("object_name")
    modifier_type = params.get("type")
    modifier_name = params.get("name")
    properties = params.get("properties")

    if not object_name:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Missing required parameter: object_name",
        )

    if not modifier_type:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Missing required parameter: type",
        )

    modifier_type = modifier_type.upper()
    if modifier_type not in VALID_MODIFIER_TYPES:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Invalid modifier type: {modifier_type}. Must be one of: {sorted(VALID_MODIFIER_TYPES)}",
        )

    validate_object_name(object_name)
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(ErrorCode.OBJECT_NOT_FOUND, f"Object '{object_name}' not found")

    # Default name to the modifier type if not provided
    if not modifier_name:
        modifier_name = modifier_type.replace("_", " ").title()

    try:
        modifier = obj.modifiers.new(name=modifier_name, type=modifier_type)
    except Exception as e:
        raise BlenderMCPError(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to add modifier '{modifier_type}' to '{object_name}': {e}",
        )

    properties_set = _set_modifier_properties(modifier, properties)

    return {
        "object_name": object_name,
        "modifier_name": modifier.name,
        "type": modifier_type,
        "properties_set": properties_set,
    }


def handle_modifier_configure(params):
    """Update properties on an existing modifier.

    params:
        object_name (str): Name of the target object.
        modifier_name (str): Name of the modifier to configure.
        properties (dict): Properties to set on the modifier.
    """
    object_name = params.get("object_name")
    modifier_name = params.get("modifier_name")
    properties = params.get("properties")

    if not object_name:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Missing required parameter: object_name",
        )

    if not modifier_name:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Missing required parameter: modifier_name",
        )

    if not properties or not isinstance(properties, dict):
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Missing or invalid required parameter: properties (must be a dict)",
        )

    validate_object_name(object_name)
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(ErrorCode.OBJECT_NOT_FOUND, f"Object '{object_name}' not found")

    modifier = obj.modifiers.get(modifier_name)
    if modifier is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Modifier '{modifier_name}' not found on object '{object_name}'",
        )

    properties_set = _set_modifier_properties(modifier, properties)

    return {
        "object_name": object_name,
        "modifier_name": modifier_name,
        "properties_set": properties_set,
    }


def handle_modifier_apply(params):
    """Apply a modifier (destructive operation).

    params:
        object_name (str): Name of the target object.
        modifier_name (str): Name of the modifier to apply.
    """
    object_name = params.get("object_name")
    modifier_name = params.get("modifier_name")

    if not object_name:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Missing required parameter: object_name",
        )

    if not modifier_name:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "Missing required parameter: modifier_name",
        )

    validate_object_name(object_name)
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(ErrorCode.OBJECT_NOT_FOUND, f"Object '{object_name}' not found")

    modifier = obj.modifiers.get(modifier_name)
    if modifier is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Modifier '{modifier_name}' not found on object '{object_name}'",
        )

    # Select and make active before applying
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    try:
        bpy.ops.object.modifier_apply(modifier=modifier_name)
    except Exception as e:
        raise BlenderMCPError(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to apply modifier '{modifier_name}' on '{object_name}': {e}",
        )

    return {
        "object_name": object_name,
        "modifier_name": modifier_name,
        "applied": True,
    }


def register():
    """Register modifier handlers with the dispatcher."""
    register_handler("modifier.add", handle_modifier_add)
    register_handler("modifier.configure", handle_modifier_configure)
    register_handler("modifier.apply", handle_modifier_apply)
