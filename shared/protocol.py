"""Wire protocol: 4-byte length-prefixed JSON framing over TCP.

Wire format: [4 bytes: big-endian uint32 length][UTF-8 JSON payload]

Uses JSON-RPC 2.0 message schema.
"""

import json
import struct
import uuid
from typing import Any

from .constants import LENGTH_PREFIX_BYTES, BYTE_ORDER, MAX_MESSAGE_SIZE
from .error_codes import ErrorCode, BlenderMCPError


def encode_message(data: dict) -> bytes:
    """Encode a dict as a length-prefixed JSON message.

    Returns: 4-byte big-endian length prefix + UTF-8 JSON payload.
    """
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise BlenderMCPError(
            ErrorCode.INTERNAL_ERROR,
            f"Message too large: {len(payload)} bytes (max {MAX_MESSAGE_SIZE})",
        )
    length_prefix = struct.pack(">I", len(payload))
    return length_prefix + payload


def decode_length_prefix(data: bytes) -> int:
    """Decode a 4-byte big-endian length prefix.

    Args:
        data: Exactly 4 bytes.

    Returns:
        The payload length as an integer.
    """
    if len(data) != LENGTH_PREFIX_BYTES:
        raise BlenderMCPError(
            ErrorCode.PARSE_ERROR,
            f"Expected {LENGTH_PREFIX_BYTES} bytes for length prefix, got {len(data)}",
        )
    return struct.unpack(">I", data)[0]


def decode_payload(data: bytes) -> dict:
    """Decode a UTF-8 JSON payload into a dict."""
    try:
        return json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise BlenderMCPError(ErrorCode.PARSE_ERROR, f"Invalid JSON payload: {e}")


def make_request(method: str, params: dict | None = None, request_id: str | None = None) -> dict:
    """Create a JSON-RPC 2.0 request message."""
    msg = {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "method": method,
    }
    if params is not None:
        msg["params"] = params
    return msg


def make_response(request_id: str, result: Any) -> dict:
    """Create a JSON-RPC 2.0 success response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def make_error_response(request_id: str | None, code: ErrorCode, message: str,
                         data: dict | None = None) -> dict:
    """Create a JSON-RPC 2.0 error response."""
    error = {"code": int(code), "message": message}
    if data:
        error["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error,
    }


def make_heartbeat() -> dict:
    """Create a heartbeat request."""
    return make_request("heartbeat")


def is_heartbeat(message: dict) -> bool:
    """Check if a message is a heartbeat."""
    return message.get("method") == "heartbeat"


# Synchronous socket helpers (used by addon which can't use asyncio)


def recv_message_sync(sock) -> dict:
    """Read one length-prefixed message from a blocking socket.

    Args:
        sock: A blocking socket.

    Returns:
        Decoded JSON dict.
    """
    # Read length prefix
    length_data = _recv_exact_sync(sock, LENGTH_PREFIX_BYTES)
    if length_data is None:
        raise BlenderMCPError(ErrorCode.CONNECTION_LOST, "Connection closed while reading length")

    payload_length = decode_length_prefix(length_data)
    if payload_length > MAX_MESSAGE_SIZE:
        raise BlenderMCPError(
            ErrorCode.PARSE_ERROR,
            f"Message too large: {payload_length} bytes",
        )

    # Read payload
    payload_data = _recv_exact_sync(sock, payload_length)
    if payload_data is None:
        raise BlenderMCPError(ErrorCode.CONNECTION_LOST, "Connection closed while reading payload")

    return decode_payload(payload_data)


def send_message_sync(sock, data: dict) -> None:
    """Send one length-prefixed message on a blocking socket."""
    sock.sendall(encode_message(data))


def _recv_exact_sync(sock, num_bytes: int) -> bytes | None:
    """Read exactly num_bytes from a blocking socket.

    Returns None if connection is closed before all bytes are read.
    """
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)
