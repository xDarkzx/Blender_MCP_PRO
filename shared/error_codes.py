"""Structured error codes for BlenderMCP."""

from enum import IntEnum


class ErrorCode(IntEnum):
    """JSON-RPC 2.0 compatible error codes.

    Standard JSON-RPC codes: -32700 to -32600
    Application codes: 1000+
    """
    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Connection errors (1000-1099)
    CONNECTION_LOST = 1000
    CONNECTION_TIMEOUT = 1001
    CONNECTION_REFUSED = 1002

    # Validation errors (2000-2099)
    OBJECT_NOT_FOUND = 2001
    MATERIAL_NOT_FOUND = 2002
    MODIFIER_NOT_FOUND = 2003
    COLLECTION_NOT_FOUND = 2004
    INVALID_OBJECT_TYPE = 2005
    INVALID_ENUM_VALUE = 2006
    VALUE_OUT_OF_RANGE = 2007
    NAME_TOO_LONG = 2008
    DUPLICATE_NAME = 2009

    # Operation errors (3000-3099)
    OPERATION_FAILED = 3000
    CONTEXT_ERROR = 3001
    MODE_ERROR = 3002
    DEPENDENCY_ERROR = 3003
    UNDO_FAILED = 3004

    # Export errors (4000-4099)
    EXPORT_FAILED = 4000
    INVALID_PATH = 4001
    INVALID_EXTENSION = 4002
    PATH_TRAVERSAL = 4003

    # Mesh errors (5000-5099)
    MESH_TOO_LARGE = 5000
    INVALID_GEOMETRY = 5001
    NON_MANIFOLD = 5002

    # Resource errors (6000-6099)
    RESOURCE_BUSY = 6000
    BATCH_TOO_LARGE = 6001


class BlenderMCPError(Exception):
    """Base exception for BlenderMCP errors."""

    def __init__(self, code: ErrorCode, message: str, data: dict | None = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert to JSON-RPC error object."""
        error = {"code": int(self.code), "message": self.message}
        if self.data:
            error["data"] = self.data
        return error
