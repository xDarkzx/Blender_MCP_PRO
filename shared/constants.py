"""Constants shared between BlenderMCP addon and server."""

# Version
VERSION = "0.1.0"

# Network
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876
LENGTH_PREFIX_BYTES = 4
MAX_MESSAGE_SIZE = 64 * 1024 * 1024  # 64 MB
BYTE_ORDER = "big"

# Heartbeat
HEARTBEAT_INTERVAL = 5.0  # seconds
HEARTBEAT_MISSED_LIMIT = 3

# Reconnection
RECONNECT_BASE_DELAY = 0.5  # seconds
RECONNECT_MAX_DELAY = 30.0
RECONNECT_MAX_ATTEMPTS = 5
RECONNECT_BACKOFF_FACTOR = 2.0

# Timeouts (seconds)
TIMEOUT_SCENE = 10
TIMEOUT_MESH = 60
TIMEOUT_EXPORT = 120
TIMEOUT_RENDER = 120
TIMEOUT_DEFAULT = 30

# Command timeout mapping (method prefix -> timeout)
TIMEOUT_MAP = {
    "scene.": TIMEOUT_SCENE,
    "mesh.": TIMEOUT_MESH,
    "export.": TIMEOUT_EXPORT,
    "viewport.screenshot": TIMEOUT_RENDER,
}

# Limits
MAX_VERTICES = 10_000_000
MAX_OBJECT_NAME_LENGTH = 63  # Blender limit
MAX_BATCH_SIZE = 1000

# Allowed export extensions
ALLOWED_EXPORT_EXTENSIONS = {".fbx", ".glb", ".gltf", ".usd", ".usda", ".usdc", ".obj", ".stl"}
