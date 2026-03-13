"""
Bulk FBX/OBJ/GLB analyzer - runs headless in Blender CLI.

Usage:
    blender --background --python bulk_analyze.py -- --input ./models/ --output ./templates/
    blender --background --python bulk_analyze.py -- --input ./models/well.fbx --output ./templates/

Scans all supported 3D files and extracts mesh profiles, materials,
hierarchy, and construction data into JSON templates for training.
"""

import bpy
import bmesh
import json
import math
import os
import sys
from pathlib import Path
from mathutils import Vector

# Parse args after "--"
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []

import argparse
parser = argparse.ArgumentParser(description="Bulk 3D model analyzer for training data")
parser.add_argument("--input", required=True, help="Input file or directory of 3D files")
parser.add_argument("--output", required=True, help="Output directory for JSON templates")
parser.add_argument("--slices", type=int, default=20, help="Number of Z-slices for profile (default: 20)")
parser.add_argument("--format", nargs="+", default=["fbx", "obj", "glb", "gltf", "blend"],
                    help="File formats to scan (default: fbx obj glb gltf blend)")
args = parser.parse_args(argv)

SUPPORTED_IMPORTERS = {
    ".fbx": lambda f: bpy.ops.import_scene.fbx(filepath=f),
    ".obj": lambda f: bpy.ops.wm.obj_import(filepath=f) if hasattr(bpy.ops.wm, 'obj_import') else bpy.ops.import_scene.obj(filepath=f),
    ".glb": lambda f: bpy.ops.import_scene.gltf(filepath=f),
    ".gltf": lambda f: bpy.ops.import_scene.gltf(filepath=f),
    ".blend": lambda f: bpy.ops.wm.open_mainfile(filepath=f),
}


def clear_scene():
    """Remove all objects from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=True)
    # Clean orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def analyze_mesh(obj, num_slices=20):
    """Analyze a single mesh object. Returns profile dict."""
    mesh = obj.data
    matrix = obj.matrix_world
    world_verts = [matrix @ v.co for v in mesh.vertices]

    if not world_verts:
        return None

    xs = [v.x for v in world_verts]
    ys = [v.y for v in world_verts]
    zs = [v.z for v in world_verts]

    bbox = {
        "min": [round(min(xs), 4), round(min(ys), 4), round(min(zs), 4)],
        "max": [round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)],
        "center": [round((min(xs)+max(xs))/2, 4), round((min(ys)+max(ys))/2, 4), round((min(zs)+max(zs))/2, 4)],
        "dimensions": [round(max(xs)-min(xs), 4), round(max(ys)-min(ys), 4), round(max(zs)-min(zs), 4)],
    }

    # Z-slice profiles
    z_min, z_max = min(zs), max(zs)
    z_range = z_max - z_min
    slices = []
    if z_range > 0.0001:
        center_x = bbox["center"][0]
        center_y = bbox["center"][1]
        for i in range(num_slices + 1):
            z = z_min + (z_range * i / num_slices)
            tolerance = z_range / (num_slices * 2)
            nearby = [v for v in world_verts if abs(v.z - z) < tolerance]
            if nearby:
                radii = [math.sqrt((v.x - center_x)**2 + (v.y - center_y)**2) for v in nearby]
                slice_xs = [v.x for v in nearby]
                slice_ys = [v.y for v in nearby]
                slices.append({
                    "z": round(z, 4),
                    "z_norm": round(i / num_slices, 3),
                    "verts": len(nearby),
                    "r_avg": round(sum(radii) / len(radii), 4),
                    "r_max": round(max(radii), 4),
                    "w_x": round(max(slice_xs) - min(slice_xs), 4),
                    "w_y": round(max(slice_ys) - min(slice_ys), 4),
                })
            else:
                slices.append({"z": round(z, 4), "z_norm": round(i / num_slices, 3), "verts": 0})

    # Materials
    materials = []
    for i, slot in enumerate(obj.material_slots):
        mat_info = {"slot": i, "name": str(slot.material.name) if slot.material else None}
        if slot.material and slot.material.use_nodes:
            for node in slot.material.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    inp = node.inputs.get("Base Color")
                    if inp and hasattr(inp, "default_value"):
                        mat_info["base_color"] = [round(c, 3) for c in inp.default_value[:3]]
                    met = node.inputs.get("Metallic")
                    if met and hasattr(met, "default_value"):
                        mat_info["metallic"] = round(met.default_value, 3)
                    rough = node.inputs.get("Roughness")
                    if rough and hasattr(rough, "default_value"):
                        mat_info["roughness"] = round(rough.default_value, 3)
                    break
        # Material zone (which Z range)
        mat_faces = [p for p in mesh.polygons if p.material_index == i]
        if mat_faces:
            face_zs = [sum(world_verts[vi].z for vi in f.vertices) / len(f.vertices) for f in mat_faces]
            mat_info["face_count"] = len(mat_faces)
            mat_info["z_range"] = [round(min(face_zs), 4), round(max(face_zs), 4)]
        materials.append(mat_info)

    # Face normal distribution
    normals = {"up": 0, "down": 0, "north": 0, "south": 0, "east": 0, "west": 0}
    for poly in mesh.polygons:
        wn = (matrix.to_3x3() @ Vector(poly.normal)).normalized()
        ax, ay, az = abs(wn.x), abs(wn.y), abs(wn.z)
        if az >= ax and az >= ay:
            normals["up" if wn.z > 0 else "down"] += 1
        elif ay >= ax:
            normals["north" if wn.y > 0 else "south"] += 1
        else:
            normals["east" if wn.x > 0 else "west"] += 1

    # Loose parts
    bm = bmesh.new()
    bm.from_mesh(mesh)
    loose_parts = 0
    visited = set()
    for v in bm.verts:
        if v.index not in visited:
            loose_parts += 1
            stack = [v]
            while stack:
                cur = stack.pop()
                if cur.index in visited:
                    continue
                visited.add(cur.index)
                for e in cur.link_edges:
                    o = e.other_vert(cur)
                    if o.index not in visited:
                        stack.append(o)
    bm.free()

    # Symmetry (sample 200 verts)
    sample = world_verts[:200] if len(world_verts) > 200 else world_verts
    tol = max(z_range * 0.01, 0.001)
    cx, cy = bbox["center"][0], bbox["center"][1]
    x_match = sum(1 for v in sample if any((Vector((2*cx - v.x, v.y, v.z)) - v2).length < tol for v2 in sample))
    y_match = sum(1 for v in sample if any((Vector((v.x, 2*cy - v.y, v.z)) - v2).length < tol for v2 in sample))
    n = len(sample)
    symmetry = {
        "x": round(x_match / n, 3) if n else 0,
        "y": round(y_match / n, 3) if n else 0,
    }

    # Modifiers
    modifiers = [{"name": m.name, "type": m.type} for m in obj.modifiers]

    return {
        "name": obj.name,
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "face_count": len(mesh.polygons),
        "loose_parts": loose_parts,
        "bounding_box": bbox,
        "z_slices": slices,
        "materials": materials,
        "face_normals": normals,
        "symmetry": symmetry,
        "modifiers": modifiers,
        "has_uvs": len(mesh.uv_layers) > 0,
        "uv_layers": len(mesh.uv_layers),
    }


def analyze_file(filepath, num_slices=20):
    """Import a 3D file and analyze all mesh objects."""
    ext = Path(filepath).suffix.lower()
    if ext not in SUPPORTED_IMPORTERS:
        print(f"  SKIP: unsupported format {ext}")
        return None

    clear_scene()

    # Import
    try:
        SUPPORTED_IMPORTERS[ext](filepath)
    except Exception as e:
        print(f"  ERROR importing: {e}")
        return None

    # Build hierarchy
    def build_hierarchy(obj):
        h = {"name": obj.name, "type": obj.type}
        if obj.children:
            h["children"] = [build_hierarchy(c) for c in obj.children]
        return h

    roots = [obj for obj in bpy.context.scene.objects if obj.parent is None]
    hierarchy = [build_hierarchy(r) for r in roots]

    # Analyze all meshes
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    parts = []
    total_verts = 0
    total_faces = 0

    for obj in mesh_objects:
        profile = analyze_mesh(obj, num_slices)
        if profile:
            parts.append(profile)
            total_verts += profile["vertex_count"]
            total_faces += profile["face_count"]

    # Overall bounding box
    all_mins = [p["bounding_box"]["min"] for p in parts]
    all_maxs = [p["bounding_box"]["max"] for p in parts]
    if all_mins and all_maxs:
        overall_min = [min(m[i] for m in all_mins) for i in range(3)]
        overall_max = [max(m[i] for m in all_maxs) for i in range(3)]
        overall_dims = [overall_max[i] - overall_min[i] for i in range(3)]
    else:
        overall_dims = [0, 0, 0]

    # Collect unique materials
    all_mats = {}
    for p in parts:
        for m in p.get("materials", []):
            if m.get("name") and m["name"] not in all_mats:
                all_mats[m["name"]] = m

    return {
        "meta": {
            "source_file": os.path.basename(filepath),
            "source_path": filepath,
            "format": ext,
            "total_objects": len(bpy.context.scene.objects),
            "mesh_objects": len(mesh_objects),
            "total_vertices": total_verts,
            "total_faces": total_faces,
            "overall_dimensions": [round(d, 4) for d in overall_dims],
        },
        "hierarchy": hierarchy,
        "materials_unique": list(all_mats.values()),
        "parts": parts,
    }


def main():
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect files
    files = []
    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        for ext in args.format:
            files.extend(input_path.rglob(f"*.{ext}"))
    else:
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    print(f"Found {len(files)} file(s) to analyze")

    results = []
    for i, f in enumerate(sorted(files)):
        print(f"\n[{i+1}/{len(files)}] Analyzing: {f.name}")
        try:
            template = analyze_file(str(f), args.slices)
            if template:
                # Save individual template
                out_name = f.stem + ".json"
                out_path = output_dir / out_name
                with open(out_path, "w") as fp:
                    json.dump(template, fp, indent=2)
                print(f"  -> {out_path} ({template['meta']['total_vertices']} verts, {template['meta']['mesh_objects']} meshes)")
                results.append({"file": f.name, "output": str(out_path), "status": "ok"})
            else:
                results.append({"file": f.name, "status": "failed"})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"file": f.name, "status": "error", "error": str(e)})

    # Write summary
    summary_path = output_dir / "_summary.json"
    with open(summary_path, "w") as fp:
        json.dump({
            "total_files": len(files),
            "successful": sum(1 for r in results if r["status"] == "ok"),
            "failed": sum(1 for r in results if r["status"] != "ok"),
            "results": results,
        }, fp, indent=2)
    print(f"\nDone! Summary: {summary_path}")
    print(f"  {sum(1 for r in results if r['status'] == 'ok')}/{len(files)} files analyzed successfully")


if __name__ == "__main__":
    main()
