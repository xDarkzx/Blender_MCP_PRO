"""Install BlenderMCP Pro addon into Blender's addons folder.

Usage: python install_addon.py
"""

import shutil
import os
import sys

# Source directories
ROOT = os.path.dirname(os.path.abspath(__file__))
ADDON_SRC = os.path.join(ROOT, "addon")
SHARED_SRC = os.path.join(ROOT, "shared")

# Find Blender addon directory
BLENDER_BASE = os.path.join(
    os.environ.get("APPDATA", ""),
    "Blender Foundation", "Blender"
)

def find_blender_versions():
    """Find all installed Blender versions."""
    versions = []
    if os.path.isdir(BLENDER_BASE):
        for entry in os.listdir(BLENDER_BASE):
            path = os.path.join(BLENDER_BASE, entry, "scripts", "addons")
            if os.path.isdir(os.path.join(BLENDER_BASE, entry)):
                versions.append((entry, path))
    return versions


def install(target_dir):
    """Install addon to target directory."""
    dest = os.path.join(target_dir, "blendermcp_pro")

    # Remove old install if exists
    if os.path.exists(dest):
        print(f"  Removing old install at {dest}")
        shutil.rmtree(dest)

    # Create destination
    os.makedirs(dest, exist_ok=True)

    # Copy addon files
    for item in os.listdir(ADDON_SRC):
        src = os.path.join(ADDON_SRC, item)
        dst = os.path.join(dest, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        elif item.endswith((".py", ".toml")):
            shutil.copy2(src, dst)

    # Copy shared module inside addon
    shared_dest = os.path.join(dest, "shared")
    shutil.copytree(SHARED_SRC, shared_dest, ignore=shutil.ignore_patterns("__pycache__"))

    print(f"  Installed to {dest}")
    return dest


def main():
    versions = find_blender_versions()
    if not versions:
        print(f"ERROR: No Blender installations found at {BLENDER_BASE}")
        sys.exit(1)

    print("Found Blender versions:")
    for ver, path in versions:
        print(f"  {ver}: {path}")

    print()

    for ver, path in versions:
        # Create addons dir if it doesn't exist
        os.makedirs(path, exist_ok=True)
        print(f"Installing for Blender {ver}...")
        install(path)

    print()
    print("DONE! Now in Blender:")
    print("  1. Edit -> Preferences -> Add-ons")
    print("  2. Search for 'BlenderMCP'")
    print("  3. Enable the checkbox")
    print("  4. Press N in viewport -> BlenderMCP tab -> Start MCP Server")


if __name__ == "__main__":
    main()
