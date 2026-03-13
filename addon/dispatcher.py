"""Command routing registry for BlenderMCP addon.

Maps method names to handler functions. NO exec/eval — all operations
are statically registered handler functions.
"""

import traceback
from typing import Callable

try:
    from .shared.error_codes import ErrorCode, BlenderMCPError
    from .shared.protocol import make_response, make_error_response
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.error_codes import ErrorCode, BlenderMCPError
    from shared.protocol import make_response, make_error_response


# Handler function type: (params: dict) -> dict
HandlerFunc = Callable[[dict], dict]

# Global handler registry
_handlers: dict[str, HandlerFunc] = {}


def register_handler(method: str, handler: HandlerFunc) -> None:
    """Register a handler function for a method name.

    Args:
        method: Dotted method name (e.g. "scene.get_info")
        handler: Function that takes params dict and returns result dict
    """
    if method in _handlers:
        raise ValueError(f"Handler already registered for method: {method}")
    _handlers[method] = handler


def unregister_handler(method: str) -> None:
    """Remove a handler registration."""
    _handlers.pop(method, None)


def get_handler(method: str) -> HandlerFunc | None:
    """Look up a handler by method name."""
    return _handlers.get(method)


def list_methods() -> list[str]:
    """List all registered method names."""
    return sorted(_handlers.keys())


def dispatch(request: dict) -> dict:
    """Dispatch a JSON-RPC 2.0 request to the appropriate handler.

    Args:
        request: Parsed JSON-RPC request dict.

    Returns:
        JSON-RPC response dict (success or error).
    """
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if not method:
        return make_error_response(
            request_id, ErrorCode.INVALID_REQUEST, "Missing 'method' field"
        )

    # Heartbeat is handled at the connection level, but handle here as fallback
    if method == "heartbeat":
        return make_response(request_id, {"status": "ok"})

    handler = get_handler(method)
    if handler is None:
        return make_error_response(
            request_id, ErrorCode.METHOD_NOT_FOUND, f"Unknown method: {method}"
        )

    try:
        result = handler(params)
        return make_response(request_id, result)
    except BlenderMCPError as e:
        return make_error_response(request_id, e.code, e.message, e.data)
    except Exception as e:
        tb = traceback.format_exc()
        return make_error_response(
            request_id,
            ErrorCode.INTERNAL_ERROR,
            f"Handler error: {str(e)}",
            {"traceback": tb},
        )


def clear_all_handlers() -> None:
    """Remove all registered handlers. Used for cleanup."""
    _handlers.clear()
