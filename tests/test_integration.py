"""Integration test: connects directly to the Blender addon over TCP.

Usage:
  1. Open Blender with the BlenderMCP addon enabled
  2. Click "Start MCP Server" in the sidebar panel
  3. Run: python tests/test_integration.py

This sends real commands to Blender and prints the results.
"""

import socket
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.protocol import send_message_sync, recv_message_sync, make_request
from shared.constants import DEFAULT_HOST, DEFAULT_PORT


def send_command(sock, method: str, params: dict = None) -> dict:
    """Send a command and wait for response."""
    request = make_request(method, params)
    print(f"\n>>> {method}({json.dumps(params) if params else ''})")
    send_message_sync(sock, request)
    response = recv_message_sync(sock)

    if "error" in response:
        print(f"  ERROR [{response['error']['code']}]: {response['error']['message']}")
    else:
        result = response.get("result", {})
        # Truncate long results for display
        result_str = json.dumps(result, indent=2)
        if len(result_str) > 500:
            result_str = result_str[:500] + "\n  ... (truncated)"
        print(f"  OK: {result_str}")

    return response


def main():
    host = DEFAULT_HOST
    port = DEFAULT_PORT

    print(f"Connecting to Blender at {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect((host, port))
        print("Connected!\n")
    except ConnectionRefusedError:
        print("ERROR: Could not connect. Make sure:")
        print("  1. Blender is running")
        print("  2. BlenderMCP addon is enabled")
        print("  3. Server is started (sidebar → BlenderMCP → Start)")
        sys.exit(1)

    try:
        # --- Test 1: Scene Info ---
        print("=" * 60)
        print("TEST 1: Get Scene Info")
        print("=" * 60)
        send_command(sock, "scene.get_info")

        # --- Test 2: List Objects ---
        print("\n" + "=" * 60)
        print("TEST 2: List Objects")
        print("=" * 60)
        send_command(sock, "scene.list_objects")

        # --- Test 3: Create a Cube ---
        print("\n" + "=" * 60)
        print("TEST 3: Create a Cube")
        print("=" * 60)
        send_command(sock, "mesh.create_primitive", {
            "type": "CUBE",
            "name": "MCP_TestCube",
            "location": [2, 0, 0],
            "size": 1.5,
        })

        # --- Test 4: Create a Sphere ---
        print("\n" + "=" * 60)
        print("TEST 4: Create a UV Sphere")
        print("=" * 60)
        send_command(sock, "mesh.create_primitive", {
            "type": "SPHERE",
            "name": "MCP_TestSphere",
            "location": [-2, 0, 0],
            "segments": 32,
            "ring_count": 16,
        })

        # --- Test 5: Get Object Details ---
        print("\n" + "=" * 60)
        print("TEST 5: Get Object Details")
        print("=" * 60)
        send_command(sock, "scene.get_object", {"name": "MCP_TestCube"})

        # --- Test 6: Create Material ---
        print("\n" + "=" * 60)
        print("TEST 6: Create PBR Material")
        print("=" * 60)
        send_command(sock, "material.create", {
            "name": "MCP_RedMetal",
            "base_color": [0.8, 0.1, 0.1, 1.0],
            "metallic": 0.9,
            "roughness": 0.2,
        })

        # --- Test 7: Assign Material ---
        print("\n" + "=" * 60)
        print("TEST 7: Assign Material to Cube")
        print("=" * 60)
        send_command(sock, "material.assign", {
            "object_name": "MCP_TestCube",
            "material_name": "MCP_RedMetal",
        })

        # --- Test 8: Add Modifier ---
        print("\n" + "=" * 60)
        print("TEST 8: Add Subdivision Surface Modifier")
        print("=" * 60)
        send_command(sock, "modifier.add", {
            "object_name": "MCP_TestCube",
            "type": "SUBSURF",
            "properties": {"levels": 2, "render_levels": 3},
        })

        # --- Test 9: Set Transform ---
        print("\n" + "=" * 60)
        print("TEST 9: Move and Rotate Cube")
        print("=" * 60)
        send_command(sock, "object.set_transform", {
            "name": "MCP_TestCube",
            "location": [3, 1, 0.5],
            "rotation": [0, 0, 0.785],  # 45 degrees in Z
        })

        # --- Test 10: Set Smooth Shading ---
        print("\n" + "=" * 60)
        print("TEST 10: Set Smooth Shading on Sphere")
        print("=" * 60)
        send_command(sock, "mesh.set_smooth_shading", {
            "object_name": "MCP_TestSphere",
            "smooth": True,
        })

        # --- Test 11: Get Hierarchy ---
        print("\n" + "=" * 60)
        print("TEST 11: Scene Hierarchy")
        print("=" * 60)
        send_command(sock, "scene.get_hierarchy")

        # --- Test 12: Duplicate Object ---
        print("\n" + "=" * 60)
        print("TEST 12: Duplicate Cube")
        print("=" * 60)
        send_command(sock, "object.duplicate", {
            "name": "MCP_TestCube",
            "new_name": "MCP_TestCube_Copy",
            "offset": [0, 3, 0],
        })

        # --- Test 13: Selection ---
        print("\n" + "=" * 60)
        print("TEST 13: Select All MCP Test Objects")
        print("=" * 60)
        send_command(sock, "selection.set", {
            "pattern": "MCP_*",
            "action": "SET",
        })

        # --- Test 14: Heartbeat ---
        print("\n" + "=" * 60)
        print("TEST 14: Heartbeat")
        print("=" * 60)
        send_command(sock, "heartbeat")

        # --- Summary ---
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETE")
        print("Check Blender viewport — you should see:")
        print("  - A subdivided cube at (3, 1, 0.5) with red metallic material")
        print("  - A smooth-shaded sphere at (-2, 0, 0)")
        print("  - A copy of the cube offset by (0, 3, 0)")
        print("=" * 60)

    finally:
        sock.close()


if __name__ == "__main__":
    main()
