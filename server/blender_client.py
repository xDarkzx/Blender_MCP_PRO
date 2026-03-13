"""Async TCP client for connecting to the Blender addon.

Features:
- Async I/O with length-prefixed framing
- Automatic reconnection with exponential backoff
- Heartbeat monitoring
- Per-command timeouts
- Auto-screenshot after scene-modifying commands
"""

import asyncio
import json
import struct
import uuid
import logging
from typing import Any

from shared.constants import (
    DEFAULT_HOST, DEFAULT_PORT, LENGTH_PREFIX_BYTES, MAX_MESSAGE_SIZE,
    HEARTBEAT_INTERVAL, HEARTBEAT_MISSED_LIMIT,
    RECONNECT_BASE_DELAY, RECONNECT_MAX_DELAY, RECONNECT_MAX_ATTEMPTS,
    RECONNECT_BACKOFF_FACTOR, TIMEOUT_DEFAULT, TIMEOUT_MAP,
)
from shared.protocol import make_request, make_heartbeat
from shared.error_codes import ErrorCode, BlenderMCPError

logger = logging.getLogger("blendermcp.client")

# Methods that modify the scene and should trigger auto-screenshots
_MODIFYING_METHODS = {
    "mesh.create_primitive", "mesh.create_custom", "mesh.edit_geometry",
    "mesh.set_smooth_shading", "mesh.separate", "mesh.join", "mesh.set_origin",
    "object.set_transform", "object.duplicate", "object.delete",
    "object.parent", "object.unparent", "object.apply_transform",
    "material.assign", "material.update",
    "modifier.add", "modifier.configure", "modifier.apply",
    "viewport.set_camera",
}


class BlenderClient:
    """Async TCP client that communicates with the Blender addon."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._pending: dict[str, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._missed_heartbeats = 0
        self.last_screenshot_path: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to the Blender addon with exponential backoff retry."""
        delay = RECONNECT_BASE_DELAY
        for attempt in range(RECONNECT_MAX_ATTEMPTS):
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=5.0,
                )
                self._connected = True
                self._missed_heartbeats = 0
                logger.info(f"Connected to Blender at {self.host}:{self.port}")

                # Start background tasks
                self._read_task = asyncio.create_task(self._read_loop())
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                return

            except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
                if attempt < RECONNECT_MAX_ATTEMPTS - 1:
                    logger.warning(
                        f"Connection attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * RECONNECT_BACKOFF_FACTOR, RECONNECT_MAX_DELAY)
                else:
                    raise BlenderMCPError(
                        ErrorCode.CONNECTION_REFUSED,
                        f"Failed to connect after {RECONNECT_MAX_ATTEMPTS} attempts. "
                        f"Is Blender running with the BlenderMCP addon enabled?",
                    )

    async def disconnect(self) -> None:
        """Disconnect from Blender."""
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except (OSError, ConnectionError):
                pass
            self._writer = None
            self._reader = None

        # Cancel all pending requests
        for future in self._pending.values():
            if not future.done():
                future.set_exception(
                    BlenderMCPError(ErrorCode.CONNECTION_LOST, "Disconnected")
                )
        self._pending.clear()

        logger.info("Disconnected from Blender")

    async def send_command(self, method: str, params: dict | None = None) -> Any:
        """Send a command to Blender and wait for the response.

        Args:
            method: The method name (e.g. "scene.get_info")
            params: Optional parameters dict

        Returns:
            The result from Blender

        Raises:
            BlenderMCPError on timeout, connection error, or Blender error
        """
        if not self._connected:
            await self.connect()

        request_id = str(uuid.uuid4())
        request = make_request(method, params, request_id)

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        try:
            # Send the request
            await self._send_message(request)

            # Wait with timeout
            timeout = self._get_timeout(method)
            result = await asyncio.wait_for(future, timeout=timeout)

            # Auto-screenshot after scene-modifying commands
            if method in _MODIFYING_METHODS:
                await self._maybe_auto_screenshot(method)

            return result

        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise BlenderMCPError(
                ErrorCode.CONNECTION_TIMEOUT,
                f"Command '{method}' timed out after {self._get_timeout(method)}s",
            )
        except Exception:
            self._pending.pop(request_id, None)
            raise

    async def _maybe_auto_screenshot(self, method: str) -> None:
        """Take an auto-screenshot if enabled. Non-blocking - failures are silently ignored."""
        import base64 as b64
        import os
        from server import auto_screenshot

        if not auto_screenshot.is_enabled():
            return

        try:
            label = method.replace(".", "_")
            path = auto_screenshot.next_path(label)
            w, h = auto_screenshot.get_resolution()

            screenshot_result = await self._send_command_internal(
                "viewport.screenshot",
                {"width": w, "height": h, "output_path": path},
            )
            if isinstance(screenshot_result, dict):
                file_path = screenshot_result.get("file_path")

                # Fallback: addon returned base64 (old version), decode to file
                if not file_path and "image_base64" in screenshot_result:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    img_bytes = b64.b64decode(screenshot_result["image_base64"])
                    with open(path, "wb") as f:
                        f.write(img_bytes)
                    file_path = path

                self.last_screenshot_path = file_path or path
            else:
                self.last_screenshot_path = path

            logger.debug(f"Auto-screenshot saved: {self.last_screenshot_path}")
        except Exception as e:
            logger.debug(f"Auto-screenshot failed (non-fatal): {e}")

    async def _send_command_internal(self, method: str, params: dict | None = None) -> Any:
        """Internal send_command that bypasses auto-screenshot (to avoid recursion)."""
        if not self._connected:
            await self.connect()

        request_id = str(uuid.uuid4())
        request = make_request(method, params, request_id)

        future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        try:
            await self._send_message(request)
            timeout = self._get_timeout(method)
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise
        except Exception:
            self._pending.pop(request_id, None)
            raise

    async def _send_message(self, data: dict) -> None:
        """Send a length-prefixed JSON message."""
        if not self._writer:
            raise BlenderMCPError(ErrorCode.CONNECTION_LOST, "Not connected")

        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(payload) > MAX_MESSAGE_SIZE:
            raise BlenderMCPError(
                ErrorCode.INTERNAL_ERROR, f"Message too large: {len(payload)} bytes"
            )

        length_prefix = struct.pack(">I", len(payload))
        async with self._lock:
            try:
                self._writer.write(length_prefix + payload)
                await self._writer.drain()
            except (ConnectionError, OSError) as e:
                self._connected = False
                raise BlenderMCPError(ErrorCode.CONNECTION_LOST, f"Send failed: {e}")

    async def _read_message(self) -> dict:
        """Read one length-prefixed JSON message."""
        if not self._reader:
            raise BlenderMCPError(ErrorCode.CONNECTION_LOST, "Not connected")

        # Read length prefix
        length_data = await self._reader.readexactly(LENGTH_PREFIX_BYTES)
        payload_length = struct.unpack(">I", length_data)[0]

        if payload_length > MAX_MESSAGE_SIZE:
            raise BlenderMCPError(
                ErrorCode.PARSE_ERROR, f"Message too large: {payload_length} bytes"
            )

        # Read payload
        payload_data = await self._reader.readexactly(payload_length)
        return json.loads(payload_data.decode("utf-8"))

    async def _read_loop(self) -> None:
        """Background task to read responses and dispatch to pending futures."""
        try:
            while self._connected:
                try:
                    message = await self._read_message()
                except (asyncio.IncompleteReadError, ConnectionError, OSError):
                    if self._connected:
                        logger.error("Connection lost during read")
                        self._connected = False
                    break

                request_id = message.get("id")
                if not request_id:
                    continue

                future = self._pending.pop(request_id, None)
                if future and not future.done():
                    if "error" in message:
                        error = message["error"]
                        future.set_exception(
                            BlenderMCPError(
                                ErrorCode(error.get("code", -32603)),
                                error.get("message", "Unknown error"),
                                error.get("data"),
                            )
                        )
                    else:
                        future.set_result(message.get("result"))

        except asyncio.CancelledError:
            return

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to detect dead connections."""
        try:
            while self._connected:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if not self._connected:
                    break

                try:
                    heartbeat = make_heartbeat()
                    request_id = heartbeat["id"]
                    future = asyncio.get_event_loop().create_future()
                    self._pending[request_id] = future

                    await self._send_message(heartbeat)
                    await asyncio.wait_for(future, timeout=HEARTBEAT_INTERVAL)
                    self._missed_heartbeats = 0

                except (asyncio.TimeoutError, BlenderMCPError):
                    self._missed_heartbeats += 1
                    logger.warning(
                        f"Missed heartbeat ({self._missed_heartbeats}/{HEARTBEAT_MISSED_LIMIT})"
                    )
                    if self._missed_heartbeats >= HEARTBEAT_MISSED_LIMIT:
                        logger.error("Too many missed heartbeats, disconnecting")
                        self._connected = False
                        break

        except asyncio.CancelledError:
            return

    def _get_timeout(self, method: str) -> float:
        """Get the timeout for a specific command method."""
        for prefix, timeout in TIMEOUT_MAP.items():
            if method.startswith(prefix):
                return timeout
        return TIMEOUT_DEFAULT
