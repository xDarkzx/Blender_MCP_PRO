import base64
import os
import tempfile

from mcp.server.fastmcp import FastMCP
from server.blender_client import BlenderClient
from server import auto_screenshot


def _screenshot_hint(client: BlenderClient) -> str:
    if client.last_screenshot_path:
        path = client.last_screenshot_path
        client.last_screenshot_path = None
        return f"\n[Auto-screenshot: {path}]"
    return ""


def register_tools(mcp: FastMCP, client: BlenderClient) -> int:

    @mcp.tool()
    async def viewport_screenshot(
        width: int = 512, height: int = 512, output_path: str = None
    ) -> str:
        """Take a screenshot of the Blender viewport and save to disk.

        Returns the file path so you can view it with the Read tool.
        Default resolution is 512x512 for fast AI feedback.
        """
        params = {"width": width, "height": height}
        if output_path:
            params["output_path"] = output_path
        result = await client.send_command("viewport.screenshot", params)
        if isinstance(result, dict):
            file_path = result.get("file_path")

            # Fallback: if addon returned base64 (old version), decode to file
            if not file_path and "image_base64" in result:
                save_path = output_path or os.path.join(
                    tempfile.gettempdir(), "blendermcp_viewport.png"
                )
                save_dir = os.path.dirname(save_path)
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                img_bytes = base64.b64decode(result["image_base64"])
                with open(save_path, "wb") as f:
                    f.write(img_bytes)
                file_path = save_path

            if file_path:
                return (
                    f"Screenshot saved to: {file_path}\n"
                    f"Resolution: {result.get('width')}x{result.get('height')}\n"
                    f"Use the Read tool on the file path above to view the image."
                )
        return f"Screenshot captured: {result}"

    @mcp.tool()
    async def viewport_set_camera(
        location: list,
        target: list,
        lens: float = 50.0,
        camera_name: str = None,
    ) -> str:
        """Set the viewport camera position, target, and lens properties."""
        params = {"location": location, "target": target, "lens": lens}
        if camera_name is not None:
            params["camera_name"] = camera_name
        result = await client.send_command("viewport.set_camera", params)
        return f"Camera set at {location} targeting {target}: {result}" + _screenshot_hint(client)

    @mcp.tool()
    async def viewport_auto_screenshot(
        enabled: bool = True,
        width: int = 512,
        height: int = 512,
    ) -> str:
        """Enable or disable automatic screenshots after every scene-modifying tool call.

        When enabled, every tool that changes the scene (create, edit, delete,
        transform, material assign, etc.) will automatically capture a viewport
        screenshot. The AI should Read the screenshot file to review its work.

        Screenshots are saved in per-session directories with sequential numbering.

        Args:
            enabled: True to enable, False to disable
            width: Screenshot width (default 512 for speed)
            height: Screenshot height (default 512 for speed)
        """
        auto_screenshot.set_enabled(enabled)
        auto_screenshot.set_resolution(width, height)
        if enabled:
            screenshot_dir = auto_screenshot.get_screenshot_dir()
            return (
                f"Auto-screenshot ENABLED at {width}x{height}.\n"
                f"Session directory: {screenshot_dir}\n"
                f"Every scene-modifying command will now capture a screenshot.\n"
                f"The latest screenshot path is available via client.last_screenshot_path.\n"
                f"Use Read tool on screenshot paths to review your work."
            )
        return "Auto-screenshot DISABLED."

    @mcp.tool()
    async def viewport_screenshot_cleanup(
        mode: str = "old_sessions",
        session_name: str = None,
    ) -> str:
        """Clean up screenshot files to free disk space.

        Args:
            mode: Cleanup mode:
                - "old_sessions": Delete all sessions except the current one
                - "specific": Delete a specific session by name
                - "list": Just list all sessions without deleting
            session_name: Required when mode is "specific"
        """
        if mode == "list":
            sessions = auto_screenshot.list_sessions()
            if not sessions:
                return "No screenshot sessions found."
            lines = ["Screenshot sessions:"]
            for s in sessions:
                current = " (CURRENT)" if s["is_current"] else ""
                lines.append(
                    f"  {s['name']}: {s['file_count']} files, "
                    f"{s['total_size_mb']} MB{current}"
                )
            return "\n".join(lines)

        elif mode == "specific":
            if not session_name:
                return "Error: session_name is required when mode is 'specific'"
            success = auto_screenshot.cleanup_session(session_name)
            if success:
                return f"Deleted session '{session_name}'."
            return f"Could not delete session '{session_name}' (not found or is current session)."

        elif mode == "old_sessions":
            count = auto_screenshot.cleanup_all_except_current()
            return f"Deleted {count} old screenshot session(s). Current session preserved."

        return f"Unknown mode: {mode}. Use 'list', 'old_sessions', or 'specific'."

    return 5
