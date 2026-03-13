"""Tests for the wire protocol module."""

import struct
import json
import pytest

from shared.protocol import (
    encode_message,
    decode_length_prefix,
    decode_payload,
    make_request,
    make_response,
    make_error_response,
    make_heartbeat,
    is_heartbeat,
)
from shared.error_codes import ErrorCode, BlenderMCPError
from shared.constants import LENGTH_PREFIX_BYTES


class TestEncodeMessage:
    def test_basic_encode(self):
        data = {"jsonrpc": "2.0", "id": "1", "method": "test"}
        result = encode_message(data)
        # First 4 bytes are length prefix
        assert len(result) > 4
        payload_len = struct.unpack(">I", result[:4])[0]
        assert payload_len == len(result) - 4
        # Payload is valid JSON
        payload = json.loads(result[4:].decode("utf-8"))
        assert payload["method"] == "test"

    def test_unicode_encode(self):
        data = {"name": "Cube\u00e9"}
        result = encode_message(data)
        payload_len = struct.unpack(">I", result[:4])[0]
        payload = result[4:].decode("utf-8")
        assert "\u00e9" in payload

    def test_roundtrip(self):
        original = {"jsonrpc": "2.0", "id": "abc", "method": "scene.get_info", "params": {"x": 1}}
        encoded = encode_message(original)
        length = decode_length_prefix(encoded[:4])
        decoded = decode_payload(encoded[4:4 + length])
        assert decoded == original


class TestDecodeLengthPrefix:
    def test_valid_prefix(self):
        data = struct.pack(">I", 42)
        assert decode_length_prefix(data) == 42

    def test_zero_length(self):
        data = struct.pack(">I", 0)
        assert decode_length_prefix(data) == 0

    def test_wrong_size_raises(self):
        with pytest.raises(BlenderMCPError) as exc_info:
            decode_length_prefix(b"\x00\x00")
        assert exc_info.value.code == ErrorCode.PARSE_ERROR


class TestDecodePayload:
    def test_valid_json(self):
        data = b'{"key": "value"}'
        result = decode_payload(data)
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(BlenderMCPError) as exc_info:
            decode_payload(b"not json")
        assert exc_info.value.code == ErrorCode.PARSE_ERROR


class TestMakeRequest:
    def test_basic_request(self):
        req = make_request("scene.get_info")
        assert req["jsonrpc"] == "2.0"
        assert req["method"] == "scene.get_info"
        assert "id" in req
        assert "params" not in req

    def test_request_with_params(self):
        req = make_request("mesh.create", {"type": "CUBE"}, "req-1")
        assert req["id"] == "req-1"
        assert req["params"]["type"] == "CUBE"


class TestMakeResponse:
    def test_success_response(self):
        resp = make_response("req-1", {"name": "Cube"})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == "req-1"
        assert resp["result"]["name"] == "Cube"


class TestMakeErrorResponse:
    def test_error_response(self):
        resp = make_error_response("req-1", ErrorCode.OBJECT_NOT_FOUND, "Not found")
        assert resp["error"]["code"] == 2001
        assert resp["error"]["message"] == "Not found"
        assert "data" not in resp["error"]

    def test_error_with_data(self):
        resp = make_error_response("req-1", ErrorCode.INTERNAL_ERROR, "Err", {"tb": "..."})
        assert resp["error"]["data"]["tb"] == "..."


class TestHeartbeat:
    def test_make_heartbeat(self):
        hb = make_heartbeat()
        assert hb["method"] == "heartbeat"
        assert is_heartbeat(hb)

    def test_non_heartbeat(self):
        msg = make_request("scene.get_info")
        assert not is_heartbeat(msg)
