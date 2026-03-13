"""Selection handler for BlenderMCP addon."""

import fnmatch

try:
    import bpy
except ImportError:
    bpy = None

try:
    from ..dispatcher import register_handler
    from ..shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from addon.dispatcher import register_handler
    from shared.error_codes import ErrorCode, BlenderMCPError

VALID_ACTIONS = {"SELECT", "DESELECT", "TOGGLE", "SET"}
VALID_TYPES = {"MESH", "CAMERA", "LIGHT", "EMPTY", "ARMATURE", "CURVE", "SURFACE", "FONT", "LATTICE"}


def handle_selection_set(params: dict) -> dict:
    """Flexible object selection.

    Params:
        names: list of object names to select
        type_filter: object type filter
        pattern: fnmatch pattern for name matching
        action: SELECT, DESELECT, TOGGLE, SET (SET deselects all first)
    """
    names = params.get("names")
    type_filter = params.get("type_filter")
    pattern = params.get("pattern")
    action = params.get("action", "SET").upper()

    if action not in VALID_ACTIONS:
        raise BlenderMCPError(
            ErrorCode.INVALID_ENUM_VALUE,
            f"Action must be one of {VALID_ACTIONS}, got '{action}'",
        )

    if type_filter:
        type_filter = type_filter.upper()
        if type_filter not in VALID_TYPES:
            raise BlenderMCPError(
                ErrorCode.INVALID_ENUM_VALUE,
                f"Type filter must be one of {VALID_TYPES}",
            )

    # Collect target objects
    targets = []
    for obj in bpy.data.objects:
        # Filter by names
        if names is not None:
            if obj.name not in names:
                continue
        # Filter by type
        if type_filter and obj.type != type_filter:
            continue
        # Filter by pattern
        if pattern and not fnmatch.fnmatch(obj.name, pattern):
            continue
        targets.append(obj)

    # If SET action, deselect everything first
    if action == "SET":
        bpy.ops.object.select_all(action="DESELECT")

    selected = []
    deselected = []

    for obj in targets:
        if action in ("SELECT", "SET"):
            obj.select_set(True)
            selected.append(obj.name)
        elif action == "DESELECT":
            obj.select_set(False)
            deselected.append(obj.name)
        elif action == "TOGGLE":
            new_state = not obj.select_get()
            obj.select_set(new_state)
            if new_state:
                selected.append(obj.name)
            else:
                deselected.append(obj.name)

    # If SET and we have targets, make first one active
    if action == "SET" and targets:
        bpy.context.view_layer.objects.active = targets[0]

    return {
        "action": action,
        "selected": selected,
        "deselected": deselected,
        "total_affected": len(selected) + len(deselected),
    }


def register():
    register_handler("selection.set", handle_selection_set)
