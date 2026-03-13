"""Input validation for BlenderMCP addon.

Every parameter is validated before any bpy call. No exec/eval anywhere.
"""

import math
import os
from typing import Any

# Import shared modules - when running inside Blender addon, we use relative imports
# but shared/ is also bundled. We handle both cases.
try:
    from .shared.constants import (
        MAX_VERTICES, MAX_OBJECT_NAME_LENGTH, MAX_BATCH_SIZE,
        ALLOWED_EXPORT_EXTENSIONS,
    )
    from .shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys
    # Allow direct import for testing
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.constants import (
        MAX_VERTICES, MAX_OBJECT_NAME_LENGTH, MAX_BATCH_SIZE,
        ALLOWED_EXPORT_EXTENSIONS,
    )
    from shared.error_codes import ErrorCode, BlenderMCPError


def validate_params(params: dict, schema: dict) -> dict:
    """Validate parameters against a schema.

    Schema format:
        {
            "param_name": {
                "type": str | int | float | bool | list | dict,
                "required": True/False,
                "default": <value>,
                "enum": [list of allowed values],
                "min": number,
                "max": number,
                "min_length": int,
                "max_length": int,
                "item_type": type,  # for lists
            }
        }

    Returns validated (and defaulted) params dict.
    Raises BlenderMCPError on validation failure.
    """
    validated = {}

    for name, rules in schema.items():
        value = params.get(name)

        # Check required
        if value is None:
            if rules.get("required", False):
                raise BlenderMCPError(
                    ErrorCode.INVALID_PARAMS,
                    f"Missing required parameter: {name}",
                )
            if "default" in rules:
                validated[name] = rules["default"]
            continue

        # Type check
        expected_type = rules.get("type")
        if expected_type is not None:
            if expected_type is float and isinstance(value, int):
                value = float(value)
            elif expected_type is int and isinstance(value, float) and value == int(value):
                value = int(value)
            if not isinstance(value, expected_type):
                raise BlenderMCPError(
                    ErrorCode.INVALID_PARAMS,
                    f"Parameter '{name}' must be {expected_type.__name__}, got {type(value).__name__}",
                )

        # Enum check
        if "enum" in rules:
            allowed = rules["enum"]
            check_val = value.upper() if isinstance(value, str) else value
            if check_val not in allowed and value not in allowed:
                raise BlenderMCPError(
                    ErrorCode.INVALID_ENUM_VALUE,
                    f"Parameter '{name}' must be one of {allowed}, got '{value}'",
                )
            if isinstance(value, str):
                value = value.upper()

        # Range checks
        if "min" in rules and value < rules["min"]:
            raise BlenderMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"Parameter '{name}' must be >= {rules['min']}, got {value}",
            )
        if "max" in rules and value > rules["max"]:
            raise BlenderMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"Parameter '{name}' must be <= {rules['max']}, got {value}",
            )

        # Length checks (strings and lists)
        if "min_length" in rules and len(value) < rules["min_length"]:
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                f"Parameter '{name}' must have at least {rules['min_length']} items/chars",
            )
        if "max_length" in rules and len(value) > rules["max_length"]:
            raise BlenderMCPError(
                ErrorCode.INVALID_PARAMS,
                f"Parameter '{name}' exceeds max length of {rules['max_length']}",
            )

        # List item type check
        if "item_type" in rules and isinstance(value, list):
            for i, item in enumerate(value):
                if not isinstance(item, rules["item_type"]):
                    raise BlenderMCPError(
                        ErrorCode.INVALID_PARAMS,
                        f"Parameter '{name}[{i}]' must be {rules['item_type'].__name__}",
                    )

        validated[name] = value

    return validated


def validate_object_name(name: str) -> str:
    """Validate a Blender object name."""
    if not name or not isinstance(name, str):
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Object name must be a non-empty string")
    if len(name) > MAX_OBJECT_NAME_LENGTH:
        raise BlenderMCPError(
            ErrorCode.NAME_TOO_LONG,
            f"Object name exceeds {MAX_OBJECT_NAME_LENGTH} characters",
        )
    return name


def validate_vector3(value: Any, name: str = "vector") -> tuple[float, float, float]:
    """Validate and convert a 3D vector (list/tuple of 3 numbers)."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Parameter '{name}' must be a list of 3 numbers, got {value}",
        )
    try:
        return tuple(float(v) for v in value)
    except (TypeError, ValueError):
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Parameter '{name}' contains non-numeric values",
        )


def validate_color(value: Any, name: str = "color") -> tuple:
    """Validate a color value (3 or 4 component, 0-1 range)."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
        raise BlenderMCPError(
            ErrorCode.INVALID_PARAMS,
            f"Parameter '{name}' must be a list of 3 or 4 numbers (RGBA), got {value}",
        )
    for i, v in enumerate(value):
        if not isinstance(v, (int, float)) or v < 0 or v > 1:
            raise BlenderMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"Color component {i} must be 0.0-1.0, got {v}",
            )
    return tuple(float(v) for v in value)


def validate_export_path(filepath: str) -> str:
    """Validate an export file path for safety."""
    if not filepath or not isinstance(filepath, str):
        raise BlenderMCPError(ErrorCode.INVALID_PATH, "Export path must be a non-empty string")

    # Check for path traversal before normalizing
    if ".." in filepath.replace("\\", "/").split("/"):
        raise BlenderMCPError(ErrorCode.PATH_TRAVERSAL, "Path traversal detected in export path")

    # Normalize path
    filepath = os.path.normpath(filepath)

    # Check extension
    _, ext = os.path.splitext(filepath)
    if ext.lower() not in ALLOWED_EXPORT_EXTENSIONS:
        raise BlenderMCPError(
            ErrorCode.INVALID_EXTENSION,
            f"Export extension '{ext}' not allowed. Allowed: {ALLOWED_EXPORT_EXTENSIONS}",
        )

    return filepath


def validate_vertices(vertices: list) -> list:
    """Validate vertex data for mesh creation."""
    if not isinstance(vertices, list) or len(vertices) == 0:
        raise BlenderMCPError(ErrorCode.INVALID_GEOMETRY, "Vertices must be a non-empty list")
    if len(vertices) > MAX_VERTICES:
        raise BlenderMCPError(
            ErrorCode.MESH_TOO_LARGE,
            f"Vertex count {len(vertices)} exceeds max {MAX_VERTICES}",
        )
    result = []
    for i, v in enumerate(vertices):
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise BlenderMCPError(
                ErrorCode.INVALID_GEOMETRY,
                f"Vertex {i} must be [x, y, z], got {v}",
            )
        result.append(tuple(float(c) for c in v))
    return result


def validate_faces(faces: list, vertex_count: int) -> list:
    """Validate face index data for mesh creation."""
    if not isinstance(faces, list):
        raise BlenderMCPError(ErrorCode.INVALID_GEOMETRY, "Faces must be a list")
    result = []
    for i, f in enumerate(faces):
        if not isinstance(f, (list, tuple)) or len(f) < 3:
            raise BlenderMCPError(
                ErrorCode.INVALID_GEOMETRY,
                f"Face {i} must have at least 3 vertices, got {f}",
            )
        for idx in f:
            if not isinstance(idx, int) or idx < 0 or idx >= vertex_count:
                raise BlenderMCPError(
                    ErrorCode.INVALID_GEOMETRY,
                    f"Face {i} has invalid vertex index {idx} (valid: 0-{vertex_count - 1})",
                )
        result.append(tuple(f))
    return result


def validate_batch_size(items: list, name: str = "items") -> None:
    """Validate batch operation size."""
    if len(items) > MAX_BATCH_SIZE:
        raise BlenderMCPError(
            ErrorCode.BATCH_TOO_LARGE,
            f"Batch size {len(items)} exceeds max {MAX_BATCH_SIZE} for '{name}'",
        )
