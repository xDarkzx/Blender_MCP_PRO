"""
Blender addon handler for material tools.

Provides create, assign, get_info, and update operations for
Principled BSDF materials.
"""

try:
    import bpy
except ImportError:
    bpy = None

try:
    from ..dispatcher import register_handler
    from ..validation import validate_object_name, validate_color
    from ..shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from addon.dispatcher import register_handler
    from addon.validation import validate_object_name, validate_color
    from shared.error_codes import ErrorCode, BlenderMCPError


def _get_principled_bsdf(mat):
    """Get the Principled BSDF node from a material's node tree.

    Returns the node or None if not found.
    """
    if not mat.use_nodes or not mat.node_tree:
        return None
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    return None


def _get_input(node, *names):
    """Get a node input by trying multiple names (handles Blender version differences).

    Returns the input socket or None if none of the names match.
    """
    for name in names:
        if name in node.inputs:
            return node.inputs[name]
    return None


def _set_input_value(node, value, *names):
    """Set a node input value by trying multiple input names.

    Returns True if the input was found and set, False otherwise.
    """
    inp = _get_input(node, *names)
    if inp is not None:
        inp.default_value = value
        return True
    return False


def _get_input_value(node, *names):
    """Get a node input's default_value by trying multiple input names.

    Returns the value or None if not found.
    """
    inp = _get_input(node, *names)
    if inp is not None:
        val = inp.default_value
        # Convert Color or Vector types to plain lists
        if hasattr(val, "__len__"):
            return list(val)
        return val
    return None


# ---------------------------------------------------------------------------
# material.create
# ---------------------------------------------------------------------------

def handle_material_create(params):
    """Create a new Principled BSDF material.

    Params:
        name (str): Material name.
        base_color (list[float]): [r, g, b, a] values in 0-1.
        metallic (float): Metallic value 0-1.
        roughness (float): Roughness value 0-1.
        emission (list[float], optional): [r, g, b] emission color.
        emission_strength (float, optional): Emission strength.
        alpha (float, optional): Alpha value 0-1.
        blend_mode (str, optional): One of OPAQUE, CLIP, HASHED, BLEND.

    Returns:
        dict with name and properties.
    """
    name = params.get("name")
    if not name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'name' is required")

    base_color = params.get("base_color")
    if base_color is None:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'base_color' is required")
    validate_color(base_color, "base_color")

    metallic = params.get("metallic")
    if metallic is None:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'metallic' is required")
    if not (0.0 <= float(metallic) <= 1.0):
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'metallic' must be between 0 and 1")

    roughness = params.get("roughness")
    if roughness is None:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'roughness' is required")
    if not (0.0 <= float(roughness) <= 1.0):
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'roughness' must be between 0 and 1")

    # Optional params
    emission = params.get("emission")
    emission_strength = params.get("emission_strength")
    alpha = params.get("alpha")
    blend_mode = params.get("blend_mode")

    if emission is not None:
        validate_color(emission, "emission")

    if alpha is not None and not (0.0 <= float(alpha) <= 1.0):
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'alpha' must be between 0 and 1")

    valid_blend_modes = {"OPAQUE", "CLIP", "HASHED", "BLEND"}
    if blend_mode is not None and blend_mode not in valid_blend_modes:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Parameter 'blend_mode' must be one of {valid_blend_modes}"
        )

    # Create material
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True

    principled = _get_principled_bsdf(mat)
    if principled is None:
        raise BlenderMCPError(
            ErrorCode.INTERNAL_ERROR,
            "Failed to find Principled BSDF node in new material"
        )

    # Set base color (ensure 4 components)
    bc = list(base_color)
    if len(bc) == 3:
        bc.append(1.0)
    _set_input_value(principled, bc, "Base Color")

    # Set metallic and roughness
    _set_input_value(principled, float(metallic), "Metallic")
    _set_input_value(principled, float(roughness), "Roughness")

    # Set optional emission
    if emission is not None:
        em = list(emission)
        # Emission Color input expects 4 components in some Blender versions
        if len(em) == 3:
            em.append(1.0)
        _set_input_value(principled, em, "Emission Color", "Emission")

    if emission_strength is not None:
        _set_input_value(principled, float(emission_strength), "Emission Strength")

    # Set optional alpha
    if alpha is not None:
        _set_input_value(principled, float(alpha), "Alpha")

    # Set blend mode (Blender 3.x uses mat.blend_method, 4.x may differ)
    if blend_mode is not None:
        if hasattr(mat, "blend_method"):
            mat.blend_method = blend_mode
        if blend_mode != "OPAQUE" and hasattr(mat, "shadow_method"):
            mat.shadow_method = "HASHED"

    # Build response properties
    properties = {
        "base_color": bc,
        "metallic": float(metallic),
        "roughness": float(roughness),
    }
    if emission is not None:
        properties["emission"] = list(emission)
    if emission_strength is not None:
        properties["emission_strength"] = float(emission_strength)
    if alpha is not None:
        properties["alpha"] = float(alpha)
    if blend_mode is not None:
        properties["blend_mode"] = blend_mode

    return {"name": mat.name, "properties": properties}


# ---------------------------------------------------------------------------
# material.assign
# ---------------------------------------------------------------------------

def handle_material_assign(params):
    """Assign a material to an object.

    Params:
        object_name (str): Name of the target object.
        material_name (str): Name of the material to assign.
        slot_index (int, optional): Slot index to replace. If not given or
            slot does not exist, appends a new slot.

    Returns:
        dict with object_name, material_name, slot_index.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'object_name' is required")

    material_name = params.get("material_name")
    if not material_name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'material_name' is required")

    validate_object_name(object_name)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Object '{object_name}' not found"
        )

    mat = bpy.data.materials.get(material_name)
    if mat is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Material '{material_name}' not found"
        )

    slot_index = params.get("slot_index")

    if slot_index is not None:
        slot_index = int(slot_index)
        if 0 <= slot_index < len(obj.material_slots):
            # Replace existing slot
            obj.material_slots[slot_index].material = mat
        else:
            # Slot index out of range, append instead
            obj.data.materials.append(mat)
            slot_index = len(obj.material_slots) - 1
    else:
        # Append new slot
        obj.data.materials.append(mat)
        slot_index = len(obj.material_slots) - 1

    return {
        "object_name": obj.name,
        "material_name": mat.name,
        "slot_index": slot_index,
    }


# ---------------------------------------------------------------------------
# material.get_info
# ---------------------------------------------------------------------------

def handle_material_get_info(params):
    """Get PBR properties from a material's Principled BSDF node.

    Params:
        material_name (str): Name of the material.

    Returns:
        dict with all PBR properties.
    """
    material_name = params.get("material_name")
    if not material_name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'material_name' is required")

    mat = bpy.data.materials.get(material_name)
    if mat is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Material '{material_name}' not found"
        )

    principled = _get_principled_bsdf(mat)
    if principled is None:
        raise BlenderMCPError(
            ErrorCode.INTERNAL_ERROR,
            f"Material '{material_name}' does not have a Principled BSDF node"
        )

    # Gather properties
    base_color = _get_input_value(principled, "Base Color")
    metallic = _get_input_value(principled, "Metallic")
    roughness = _get_input_value(principled, "Roughness")
    specular = _get_input_value(principled, "Specular IOR Level", "Specular")
    emission = _get_input_value(principled, "Emission Color", "Emission")
    emission_strength = _get_input_value(principled, "Emission Strength")
    alpha_val = _get_input_value(principled, "Alpha")
    normal_strength = None

    # Check for normal map node connected to Normal input
    normal_input = _get_input(principled, "Normal")
    if normal_input is not None and normal_input.links:
        from_node = normal_input.links[0].from_node
        if from_node.type == "NORMAL_MAP" and "Strength" in from_node.inputs:
            normal_strength = from_node.inputs["Strength"].default_value

    # Count nodes and check for image textures
    node_count = len(mat.node_tree.nodes) if mat.node_tree else 0
    has_image_textures = False
    if mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                has_image_textures = True
                break

    return {
        "name": mat.name,
        "base_color": base_color,
        "metallic": metallic,
        "roughness": roughness,
        "specular": specular,
        "emission": emission,
        "emission_strength": emission_strength,
        "alpha": alpha_val,
        "normal_strength": normal_strength,
        "node_count": node_count,
        "has_image_textures": has_image_textures,
    }


# ---------------------------------------------------------------------------
# material.update
# ---------------------------------------------------------------------------

def handle_material_update(params):
    """Update PBR properties on an existing material's Principled BSDF.

    Params:
        material_name (str): Name of the material.
        base_color (list[float], optional): [r, g, b, a] values in 0-1.
        metallic (float, optional): Metallic value 0-1.
        roughness (float, optional): Roughness value 0-1.
        specular (float, optional): Specular value 0-1.
        emission (list[float], optional): [r, g, b] emission color.
        emission_strength (float, optional): Emission strength.
        alpha (float, optional): Alpha value 0-1.

    Returns:
        dict with name and updated_properties.
    """
    material_name = params.get("material_name")
    if not material_name:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'material_name' is required")

    mat = bpy.data.materials.get(material_name)
    if mat is None:
        raise BlenderMCPError(
            ErrorCode.OBJECT_NOT_FOUND,
            f"Material '{material_name}' not found"
        )

    principled = _get_principled_bsdf(mat)
    if principled is None:
        raise BlenderMCPError(
            ErrorCode.INTERNAL_ERROR,
            f"Material '{material_name}' does not have a Principled BSDF node"
        )

    updated_properties = {}

    # Base Color
    base_color = params.get("base_color")
    if base_color is not None:
        validate_color(base_color, "base_color")
        bc = list(base_color)
        if len(bc) == 3:
            bc.append(1.0)
        _set_input_value(principled, bc, "Base Color")
        updated_properties["base_color"] = bc

    # Metallic
    metallic = params.get("metallic")
    if metallic is not None:
        metallic = float(metallic)
        if not (0.0 <= metallic <= 1.0):
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'metallic' must be between 0 and 1")
        _set_input_value(principled, metallic, "Metallic")
        updated_properties["metallic"] = metallic

    # Roughness
    roughness = params.get("roughness")
    if roughness is not None:
        roughness = float(roughness)
        if not (0.0 <= roughness <= 1.0):
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'roughness' must be between 0 and 1")
        _set_input_value(principled, roughness, "Roughness")
        updated_properties["roughness"] = roughness

    # Specular
    specular = params.get("specular")
    if specular is not None:
        specular = float(specular)
        if not (0.0 <= specular <= 1.0):
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'specular' must be between 0 and 1")
        _set_input_value(principled, specular, "Specular IOR Level", "Specular")
        updated_properties["specular"] = specular

    # Emission
    emission = params.get("emission")
    if emission is not None:
        validate_color(emission, "emission")
        em = list(emission)
        if len(em) == 3:
            em.append(1.0)
        _set_input_value(principled, em, "Emission Color", "Emission")
        updated_properties["emission"] = list(emission)

    # Emission Strength
    emission_strength = params.get("emission_strength")
    if emission_strength is not None:
        emission_strength = float(emission_strength)
        _set_input_value(principled, emission_strength, "Emission Strength")
        updated_properties["emission_strength"] = emission_strength

    # Alpha
    alpha = params.get("alpha")
    if alpha is not None:
        alpha = float(alpha)
        if not (0.0 <= alpha <= 1.0):
            raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Parameter 'alpha' must be between 0 and 1")
        _set_input_value(principled, alpha, "Alpha")
        updated_properties["alpha"] = alpha

    if not updated_properties:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            "No properties provided to update. Supply at least one of: "
            "base_color, metallic, roughness, specular, emission, emission_strength, alpha"
        )

    return {"name": mat.name, "updated_properties": updated_properties}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    """Register all material handlers with the dispatcher."""
    register_handler("material.create", handle_material_create)
    register_handler("material.assign", handle_material_assign)
    register_handler("material.get_info", handle_material_get_info)
    register_handler("material.update", handle_material_update)
