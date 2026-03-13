"""Build the Blender addon/extension zip file.

Bundles addon/ and shared/ into a single installable zip.
For Blender 4.2+/5.x: blender_manifest.toml and __init__.py at zip root.

Usage: python build_addon.py
Output: blendermcp_addon.zip
"""

import zipfile
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(ROOT, "blendermcp_addon.zip")


def build():
    files_added = 0
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add addon/ files at the zip root (no wrapping folder)
        addon_dir = os.path.join(ROOT, "addon")
        for dirpath, dirnames, filenames in os.walk(addon_dir):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fname in filenames:
                if fname.endswith((".py", ".toml")):
                    full_path = os.path.join(dirpath, fname)
                    # Path relative to addon/ goes at zip root
                    rel_path = os.path.relpath(full_path, addon_dir)
                    zf.write(full_path, rel_path)
                    files_added += 1

        # Add shared/ as a subpackage at zip root
        shared_dir = os.path.join(ROOT, "shared")
        for dirpath, dirnames, filenames in os.walk(shared_dir):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fname in filenames:
                if fname.endswith(".py"):
                    full_path = os.path.join(dirpath, fname)
                    rel_path = os.path.relpath(full_path, shared_dir)
                    arc_path = os.path.join("shared", rel_path)
                    zf.write(full_path, arc_path)
                    files_added += 1

    print(f"Built {OUTPUT}")
    print(f"  {files_added} files added")

    # Show zip contents
    print("\nZip contents:")
    with zipfile.ZipFile(OUTPUT, "r") as zf:
        for name in sorted(zf.namelist()):
            print(f"  {name}")

    print(f"\nInstall in Blender 5.x:")
    print(f"  Edit -> Preferences -> Get Extensions -> dropdown arrow -> Install from Disk")
    print(f"  Select: {OUTPUT}")


if __name__ == "__main__":
    build()
