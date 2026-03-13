"""Viewport handlers for BlenderMCP addon."""

import base64
import tempfile
import os
import math

try:
    import bpy
except ImportError:
    bpy = None

try:
    from ..dispatcher import register_handler
    from ..validation import validate_vector3
    from ..shared.error_codes import ErrorCode, BlenderMCPError
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from addon.dispatcher import register_handler
    from addon.validation import validate_vector3
    from shared.error_codes import ErrorCode, BlenderMCPError


def handle_viewport_screenshot(params: dict) -> dict:
    """Capture viewport as PNG saved to disk.

    Returns the file path so the AI can read the image directly,
    instead of sending huge base64 blobs over the wire.
    """
    width = params.get("width", 1920)
    height = params.get("height", 1080)
    output_path = params.get("output_path", None)

    if not isinstance(width, int) or width < 64 or width > 7680:
        raise BlenderMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Width must be 64-7680")
    if not isinstance(height, int) or height < 64 or height > 4320:
        raise BlenderMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Height must be 64-4320")

    # Determine save path - use output_path if given, else a stable temp location
    if output_path:
        save_path = output_path
    else:
        save_path = os.path.join(tempfile.gettempdir(), "blendermcp_viewport.png")

    # Ensure parent directory exists
    save_dir = os.path.dirname(save_path)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)

    # Use offscreen render of the 3D viewport
    scene = bpy.context.scene
    old_res_x = scene.render.resolution_x
    old_res_y = scene.render.resolution_y
    old_res_pct = scene.render.resolution_percentage
    old_filepath = scene.render.filepath
    old_format = scene.render.image_settings.file_format

    try:
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = 100
        scene.render.filepath = save_path
        scene.render.image_settings.file_format = "PNG"

        # Use OpenGL render for viewport capture
        bpy.ops.render.opengl(write_still=True)

        file_size = os.path.getsize(save_path) if os.path.exists(save_path) else 0

        return {
            "file_path": save_path,
            "width": width,
            "height": height,
            "format": "PNG",
            "size_bytes": file_size,
        }
    finally:
        scene.render.resolution_x = old_res_x
        scene.render.resolution_y = old_res_y
        scene.render.resolution_percentage = old_res_pct
        scene.render.filepath = old_filepath
        scene.render.image_settings.file_format = old_format


def handle_viewport_set_camera(params: dict) -> dict:
    """Position/create camera and set as active."""
    location = validate_vector3(params.get("location"), "location")
    target = validate_vector3(params.get("target"), "target")
    lens = params.get("lens", 50.0)

    if location is None:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: location")
    if target is None:
        raise BlenderMCPError(ErrorCode.INVALID_PARAMS, "Missing required parameter: target")

    if not isinstance(lens, (int, float)) or lens < 1 or lens > 500:
        raise BlenderMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Lens must be 1-500mm")

    # Find or create camera
    camera_name = params.get("camera_name", "MCPCamera")
    cam = bpy.data.objects.get(camera_name)

    if cam is None or cam.type != "CAMERA":
        cam_data = bpy.data.cameras.new(camera_name)
        cam = bpy.data.objects.new(camera_name, cam_data)
        bpy.context.collection.objects.link(cam)
    else:
        cam_data = cam.data

    # Set camera properties
    cam_data.lens = float(lens)
    cam.location = location

    # Point camera at target using track_to constraint or direct calculation
    import mathutils
    direction = mathutils.Vector(target) - mathutils.Vector(location)
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot_quat.to_euler()

    # Set as active camera
    bpy.context.scene.camera = cam

    return {
        "camera_name": cam.name,
        "location": list(cam.location),
        "rotation": list(cam.rotation_euler),
        "lens": cam_data.lens,
        "target": list(target),
    }


def register():
    register_handler("viewport.screenshot", handle_viewport_screenshot)
    register_handler("viewport.set_camera", handle_viewport_set_camera)
