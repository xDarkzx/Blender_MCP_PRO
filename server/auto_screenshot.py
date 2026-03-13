"""Auto-screenshot module for BlenderMCP.

Provides automatic viewport captures after scene-modifying commands,
giving the AI visual feedback on every change.

Screenshots are saved in per-session directories for easy cleanup.
"""

import os
import shutil
import tempfile
import time
import logging

logger = logging.getLogger("blendermcp.autoscreenshot")

# Shared state
_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots")
_session_dir: str | None = None
_counter = 0
_enabled = False
_width = 512
_height = 512


def get_screenshot_dir() -> str:
    """Get the current session screenshot directory."""
    return _session_dir or _base_dir


def is_enabled() -> bool:
    return _enabled


def set_enabled(enabled: bool) -> None:
    global _enabled, _session_dir, _counter
    _enabled = enabled
    if enabled:
        # Create a new session directory with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        _session_dir = os.path.join(_base_dir, f"session_{timestamp}")
        os.makedirs(_session_dir, exist_ok=True)
        _counter = 0
        logger.info(f"Auto-screenshot enabled, session dir: {_session_dir}")
    else:
        logger.info("Auto-screenshot disabled")


def set_resolution(width: int, height: int) -> None:
    global _width, _height
    _width = max(64, min(width, 1920))
    _height = max(64, min(height, 1920))


def get_resolution() -> tuple[int, int]:
    return _width, _height


def next_path(label: str = "") -> str:
    """Get the next sequential screenshot path."""
    global _counter
    _counter += 1
    directory = _session_dir or _base_dir
    os.makedirs(directory, exist_ok=True)
    safe_label = label.replace(".", "_").replace(" ", "_")[:30]
    filename = f"{_counter:04d}_{safe_label}.png"
    return os.path.join(directory, filename)


def get_counter() -> int:
    return _counter


def list_sessions() -> list[dict]:
    """List all screenshot sessions with their file counts and sizes."""
    sessions = []
    if not os.path.exists(_base_dir):
        return sessions

    for entry in sorted(os.listdir(_base_dir)):
        session_path = os.path.join(_base_dir, entry)
        if os.path.isdir(session_path):
            files = [f for f in os.listdir(session_path) if f.endswith(".png")]
            total_size = sum(
                os.path.getsize(os.path.join(session_path, f)) for f in files
            )
            sessions.append({
                "name": entry,
                "path": session_path,
                "file_count": len(files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "is_current": session_path == _session_dir,
            })
    return sessions


def cleanup_session(session_name: str) -> bool:
    """Delete a specific screenshot session directory."""
    session_path = os.path.join(_base_dir, session_name)
    if os.path.exists(session_path) and os.path.isdir(session_path):
        # Don't delete the active session
        if session_path == _session_dir:
            return False
        shutil.rmtree(session_path)
        return True
    return False


def cleanup_all_except_current() -> int:
    """Delete all screenshot sessions except the current one. Returns count deleted."""
    deleted = 0
    if not os.path.exists(_base_dir):
        return 0

    for entry in os.listdir(_base_dir):
        session_path = os.path.join(_base_dir, entry)
        if os.path.isdir(session_path) and session_path != _session_dir:
            shutil.rmtree(session_path)
            deleted += 1
    return deleted


def reset() -> None:
    """Reset counter (e.g., at start of new session)."""
    global _counter
    _counter = 0
