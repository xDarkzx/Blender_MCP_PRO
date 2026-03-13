"""TCP socket server running inside Blender.

Listens on localhost for connections from the MCP server.
Uses Blender's timer system to bridge between the socket thread
and Blender's main thread (bpy operations must run on main thread).
"""

import socket
import threading
import queue
import time

try:
    import bpy
except ImportError:
    bpy = None  # Allow importing for tests

try:
    from .shared.constants import DEFAULT_HOST, DEFAULT_PORT, HEARTBEAT_INTERVAL
    from .shared.protocol import (
        recv_message_sync, send_message_sync,
        make_response, is_heartbeat,
    )
    from .shared.error_codes import ErrorCode, BlenderMCPError
    from .dispatcher import dispatch
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.constants import DEFAULT_HOST, DEFAULT_PORT, HEARTBEAT_INTERVAL
    from shared.protocol import (
        recv_message_sync, send_message_sync,
        make_response, is_heartbeat,
    )
    from shared.error_codes import ErrorCode, BlenderMCPError
    from addon.dispatcher import dispatch


class BlenderTCPServer:
    """TCP server that runs inside Blender, bridging socket I/O to main thread."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._server_socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._request_queue: queue.Queue = queue.Queue()
        self._response_queue: queue.Queue = queue.Queue()
        self._connected = False
        self._timer_registered = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        """Start the TCP server."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._server_loop, daemon=True)
        self._thread.start()

        # Register Blender timer to process requests on main thread
        if bpy and not self._timer_registered:
            bpy.app.timers.register(self._process_requests, first_interval=0.05, persistent=True)
            self._timer_registered = True

    def stop(self) -> None:
        """Stop the TCP server and clean up."""
        self._running = False

        if self._client_socket:
            try:
                self._client_socket.close()
            except OSError:
                pass
            self._client_socket = None
            self._connected = False

        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        # Unregister timer
        if bpy and self._timer_registered:
            try:
                bpy.app.timers.unregister(self._process_requests)
            except ValueError:
                pass
            self._timer_registered = False

        # Clear queues
        while not self._request_queue.empty():
            try:
                self._request_queue.get_nowait()
            except queue.Empty:
                break
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break

    def _server_loop(self) -> None:
        """Main server loop running in background thread."""
        while self._running:
            try:
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._server_socket.settimeout(1.0)
                self._server_socket.bind((self.host, self.port))
                self._server_socket.listen(1)
                break
            except OSError as e:
                if self._running:
                    time.sleep(1.0)
                    continue
                return

        while self._running:
            # Accept connections
            try:
                client, addr = self._server_socket.accept()
                client.settimeout(HEARTBEAT_INTERVAL * 4)
                with self._lock:
                    # Close any existing connection
                    if self._client_socket:
                        try:
                            self._client_socket.close()
                        except OSError:
                            pass
                    self._client_socket = client
                    self._connected = True
                self._handle_client(client)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    time.sleep(0.5)

    def _handle_client(self, client: socket.socket) -> None:
        """Handle a single client connection."""
        try:
            while self._running:
                try:
                    message = recv_message_sync(client)
                except BlenderMCPError:
                    break
                except (ConnectionError, OSError):
                    break

                # Handle heartbeat directly in the socket thread
                if is_heartbeat(message):
                    try:
                        response = make_response(message.get("id"), {"status": "ok"})
                        send_message_sync(client, response)
                    except (ConnectionError, OSError):
                        break
                    continue

                # Queue request for main thread processing
                response_event = threading.Event()
                self._request_queue.put((message, response_event))

                # Wait for main thread to process and respond
                response_event.wait(timeout=120.0)

                # Get response from response queue
                try:
                    response = self._response_queue.get_nowait()
                    send_message_sync(client, response)
                except queue.Empty:
                    pass
                except (ConnectionError, OSError):
                    break
        finally:
            with self._lock:
                if self._client_socket is client:
                    self._connected = False
                    self._client_socket = None
            try:
                client.close()
            except OSError:
                pass

    def _process_requests(self) -> float | None:
        """Blender timer callback: process queued requests on main thread.

        Returns interval for next call, or None to unregister.
        """
        if not self._running:
            self._timer_registered = False
            return None

        try:
            message, response_event = self._request_queue.get_nowait()
        except queue.Empty:
            return 0.05  # Check again in 50ms

        # Dispatch on main thread (safe for bpy operations)
        response = dispatch(message)
        self._response_queue.put(response)
        response_event.set()

        return 0.01  # Process next request quickly if queued


# Module-level server instance
_server_instance: BlenderTCPServer | None = None


def get_server() -> BlenderTCPServer | None:
    """Get the current server instance."""
    return _server_instance


def start_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> BlenderTCPServer:
    """Start the global server instance."""
    global _server_instance
    if _server_instance and _server_instance.is_running:
        _server_instance.stop()
    _server_instance = BlenderTCPServer(host, port)
    _server_instance.start()
    return _server_instance


def stop_server() -> None:
    """Stop the global server instance."""
    global _server_instance
    if _server_instance:
        _server_instance.stop()
        _server_instance = None
