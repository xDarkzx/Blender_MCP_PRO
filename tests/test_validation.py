"""Tests for the validation module."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.error_codes import ErrorCode, BlenderMCPError
from addon.validation import (
    validate_params,
    validate_object_name,
    validate_vector3,
    validate_color,
    validate_export_path,
    validate_vertices,
    validate_faces,
)


class TestValidateParams:
    def test_required_present(self):
        schema = {"name": {"type": str, "required": True}}
        result = validate_params({"name": "Cube"}, schema)
        assert result["name"] == "Cube"

    def test_required_missing(self):
        schema = {"name": {"type": str, "required": True}}
        with pytest.raises(BlenderMCPError) as exc_info:
            validate_params({}, schema)
        assert exc_info.value.code == ErrorCode.INVALID_PARAMS

    def test_default_value(self):
        schema = {"smooth": {"type": bool, "default": True}}
        result = validate_params({}, schema)
        assert result["smooth"] is True

    def test_type_check(self):
        schema = {"count": {"type": int}}
        with pytest.raises(BlenderMCPError):
            validate_params({"count": "five"}, schema)

    def test_int_float_coercion(self):
        schema = {"value": {"type": float}}
        result = validate_params({"value": 5}, schema)
        assert isinstance(result["value"], float)
        assert result["value"] == 5.0

    def test_enum_check(self):
        schema = {"type": {"type": str, "enum": ["CUBE", "SPHERE"]}}
        result = validate_params({"type": "cube"}, schema)
        assert result["type"] == "CUBE"

    def test_enum_invalid(self):
        schema = {"type": {"type": str, "enum": ["CUBE", "SPHERE"]}}
        with pytest.raises(BlenderMCPError) as exc_info:
            validate_params({"type": "BANANA"}, schema)
        assert exc_info.value.code == ErrorCode.INVALID_ENUM_VALUE

    def test_range_min(self):
        schema = {"x": {"type": float, "min": 0.0}}
        with pytest.raises(BlenderMCPError) as exc_info:
            validate_params({"x": -1.0}, schema)
        assert exc_info.value.code == ErrorCode.VALUE_OUT_OF_RANGE

    def test_range_max(self):
        schema = {"x": {"type": float, "max": 100.0}}
        with pytest.raises(BlenderMCPError):
            validate_params({"x": 101.0}, schema)

    def test_max_length(self):
        schema = {"name": {"type": str, "max_length": 5}}
        with pytest.raises(BlenderMCPError):
            validate_params({"name": "toolong"}, schema)

    def test_optional_absent(self):
        schema = {"name": {"type": str}}
        result = validate_params({}, schema)
        assert "name" not in result


class TestValidateObjectName:
    def test_valid_name(self):
        assert validate_object_name("Cube") == "Cube"

    def test_empty_name(self):
        with pytest.raises(BlenderMCPError):
            validate_object_name("")

    def test_too_long(self):
        with pytest.raises(BlenderMCPError) as exc_info:
            validate_object_name("x" * 64)
        assert exc_info.value.code == ErrorCode.NAME_TOO_LONG


class TestValidateVector3:
    def test_valid_vector(self):
        result = validate_vector3([1.0, 2.0, 3.0])
        assert result == (1.0, 2.0, 3.0)

    def test_int_coercion(self):
        result = validate_vector3([1, 2, 3])
        assert all(isinstance(v, float) for v in result)

    def test_none_returns_none(self):
        assert validate_vector3(None) is None

    def test_wrong_length(self):
        with pytest.raises(BlenderMCPError):
            validate_vector3([1, 2])

    def test_non_numeric(self):
        with pytest.raises(BlenderMCPError):
            validate_vector3([1, "a", 3])


class TestValidateColor:
    def test_valid_rgb(self):
        result = validate_color([1.0, 0.5, 0.0])
        assert result == (1.0, 0.5, 0.0)

    def test_valid_rgba(self):
        result = validate_color([1.0, 0.5, 0.0, 0.8])
        assert len(result) == 4

    def test_out_of_range(self):
        with pytest.raises(BlenderMCPError):
            validate_color([1.5, 0.0, 0.0])

    def test_none_returns_none(self):
        assert validate_color(None) is None


class TestValidateExportPath:
    def test_valid_fbx(self):
        result = validate_export_path("/tmp/model.fbx")
        assert result.endswith("model.fbx")

    def test_invalid_extension(self):
        with pytest.raises(BlenderMCPError) as exc_info:
            validate_export_path("/tmp/model.exe")
        assert exc_info.value.code == ErrorCode.INVALID_EXTENSION

    def test_path_traversal(self):
        with pytest.raises(BlenderMCPError) as exc_info:
            validate_export_path("/tmp/../etc/model.fbx")
        assert exc_info.value.code == ErrorCode.PATH_TRAVERSAL

    def test_empty_path(self):
        with pytest.raises(BlenderMCPError):
            validate_export_path("")


class TestValidateVertices:
    def test_valid_vertices(self):
        verts = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        result = validate_vertices(verts)
        assert len(result) == 3

    def test_empty_vertices(self):
        with pytest.raises(BlenderMCPError):
            validate_vertices([])

    def test_invalid_vertex(self):
        with pytest.raises(BlenderMCPError):
            validate_vertices([[0, 0]])  # Only 2 components


class TestValidateFaces:
    def test_valid_faces(self):
        result = validate_faces([[0, 1, 2]], 3)
        assert result == [(0, 1, 2)]

    def test_index_out_of_range(self):
        with pytest.raises(BlenderMCPError):
            validate_faces([[0, 1, 5]], 3)

    def test_face_too_few_verts(self):
        with pytest.raises(BlenderMCPError):
            validate_faces([[0, 1]], 3)
