"""
FBX/OBJ/GLB to MCP recipe converter - extracts exact geometry as mesh_create_custom calls.

Imports a 3D file in headless Blender, reads every vertex and face,
and outputs MCP tool-call sequences that recreate the model exactly.

Usage:
    blender --background --python fbx_to_recipe.py -- --input ./models/tank.fbx --output ./recipes/
    blender --background --python fbx_to_recipe.py -- --input ./models/ --output ./recipes/ --max-verts 5000
"""

import bpy
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
parser = argparse.ArgumentParser(description="FBX to MCP recipe converter")
parser.add_argument("--input", required=True, help="Input file or directory")
parser.add_argument("--output", required=True, help="Output directory for recipe JSON")
parser.add_argument("--max-verts", type=int, default=10000,
                    help="Skip meshes with more vertices than this (default: 10000)")
parser.add_argument("--decimals", type=int, default=4,
                    help="Decimal places for vertex coords (default: 4)")
parser.add_argument("--format", nargs="+", default=["fbx", "obj", "glb", "gltf"],
                    help="File formats to scan")
parser.add_argument("--decimate", type=float, default=None,
                    help="Decimate ratio (0.1-1.0) to reduce poly count before export")
parser.add_argument("--chatml", action="store_true",
                    help="Also output ChatML training format")
args = parser.parse_args(argv)

SUPPORTED_IMPORTERS = {
    ".fbx": lambda f: bpy.ops.import_scene.fbx(filepath=f),
    ".obj": lambda f: bpy.ops.wm.obj_import(filepath=f) if hasattr(bpy.ops.wm, 'obj_import') else bpy.ops.import_scene.obj(filepath=f),
    ".glb": lambda f: bpy.ops.import_scene.gltf(filepath=f),
    ".gltf": lambda f: bpy.ops.import_scene.gltf(filepath=f),
}


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=True)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def extract_material_info(obj):
    """Extract material data from object."""
    materials = []
    for i, slot in enumerate(obj.material_slots):
        if not slot.material:
            continue
        mat = slot.material
        mat_info = {"name": mat.name, "slot": i}
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
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
        materials.append(mat_info)
    return materials


def mesh_to_tool_calls(obj, decimals=4):
    """Convert a mesh object to MCP tool calls."""
    mesh = obj.data
    matrix = obj.matrix_world

    # Get world-space vertices
    verts = []
    for v in mesh.vertices:
        world_co = matrix @ v.co
        verts.append([round(world_co.x, decimals),
                      round(world_co.y, decimals),
                      round(world_co.z, decimals)])

    # Get faces (as vertex index lists)
    faces = []
    for poly in mesh.polygons:
        faces.append(list(poly.vertices))

    # Get edges that aren't part of faces (loose edges)
    face_edges = set()
    for poly in mesh.polygons:
        for i in range(len(poly.vertices)):
            v1 = poly.vertices[i]
            v2 = poly.vertices[(i + 1) % len(poly.vertices)]
            face_edges.add((min(v1, v2), max(v1, v2)))

    loose_edges = []
    for edge in mesh.edges:
        key = (min(edge.vertices[0], edge.vertices[1]),
               max(edge.vertices[0], edge.vertices[1]))
        if key not in face_edges:
            loose_edges.append(list(edge.vertices))

    tools = []

    # Create the mesh
    create_params = {
        "vertices": verts,
        "faces": faces,
        "name": obj.name,
    }
    if loose_edges:
        create_params["edges"] = loose_edges

    tools.append({
        "tool": "mesh_create_custom",
        "params": create_params,
    })

    # Materials
    mat_infos = extract_material_info(obj)
    for mat_info in mat_infos:
        create_mat = {
            "tool": "material_create",
            "params": {
                "name": mat_info["name"],
                "base_color": mat_info.get("base_color", [0.8, 0.8, 0.8]),
            }
        }
        if "metallic" in mat_info:
            create_mat["params"]["metallic"] = mat_info["metallic"]
        if "roughness" in mat_info:
            create_mat["params"]["roughness"] = mat_info["roughness"]
        tools.append(create_mat)

        tools.append({
            "tool": "material_assign",
            "params": {
                "object_name": obj.name,
                "material_name": mat_info["name"],
                "slot_index": mat_info["slot"],
            }
        })

    # Smooth shading if object has smooth faces
    has_smooth = any(p.use_smooth for p in mesh.polygons)
    if has_smooth:
        tools.append({
            "tool": "mesh_set_smooth_shading",
            "params": {"object_name": obj.name, "smooth": True}
        })

    return tools


def process_file(filepath, max_verts, decimals, decimate_ratio=None):
    """Import a file and convert all meshes to tool calls."""
    ext = Path(filepath).suffix.lower()
    if ext not in SUPPORTED_IMPORTERS:
        return None

    clear_scene()

    try:
        SUPPORTED_IMPORTERS[ext](filepath)
    except Exception as e:
        print(f"  ERROR importing: {e}")
        return None

    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not mesh_objects:
        print(f"  No mesh objects found")
        return None

    # Optional decimation
    if decimate_ratio and decimate_ratio < 1.0:
        for obj in mesh_objects:
            if len(obj.data.vertices) > 100:  # don't decimate tiny meshes
                mod = obj.modifiers.new("Decimate", 'DECIMATE')
                mod.ratio = decimate_ratio
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.modifier_apply(modifier="Decimate")

    all_tools = []
    total_verts = 0
    skipped = 0
    parts_info = []

    for obj in mesh_objects:
        n_verts = len(obj.data.vertices)
        n_faces = len(obj.data.polygons)

        if n_verts > max_verts:
            print(f"  SKIP {obj.name}: {n_verts} verts > {max_verts} max")
            skipped += 1
            continue

        tools = mesh_to_tool_calls(obj, decimals)
        all_tools.extend(tools)
        total_verts += n_verts
        parts_info.append({
            "name": obj.name,
            "vertices": n_verts,
            "faces": n_faces,
        })

    # Calculate overall bounding box for description
    all_verts = []
    for obj in mesh_objects:
        if len(obj.data.vertices) <= max_verts:
            matrix = obj.matrix_world
            for v in obj.data.vertices:
                wv = matrix @ v.co
                all_verts.append(wv)

    if not all_verts:
        return None

    bbox_min = [min(v[i] for v in all_verts) for i in range(3)]
    bbox_max = [max(v[i] for v in all_verts) for i in range(3)]
    dims = [round(bbox_max[i] - bbox_min[i], 3) for i in range(3)]

    model_name = Path(filepath).stem

    # Auto-generate description from filename
    # Convert CamelCase and underscores to words
    import re
    words = re.sub(r'([A-Z])', r' \1', model_name)
    words = words.replace('_', ' ').replace('-', ' ').strip()

    return {
        "meta": {
            "source_file": os.path.basename(filepath),
            "model_name": model_name,
            "description": f"Create a 3D model of {words}",
            "total_vertices": total_verts,
            "total_faces": sum(p["faces"] for p in parts_info),
            "parts": len(parts_info),
            "skipped_parts": skipped,
            "dimensions": dims,
        },
        "prompt": f"Create a 3D model of {words} ({dims[0]}m x {dims[1]}m x {dims[2]}m, {len(parts_info)} parts)",
        "tools": all_tools,
        "tool_count": len(all_tools),
        "parts_info": parts_info,
    }


def main():
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = []
    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        for ext in args.format:
            files.extend(input_path.rglob(f"*.{ext}"))
    else:
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    print(f"Found {len(files)} file(s) to convert")
    print(f"Max verts per mesh: {args.max_verts}")
    if args.decimate:
        print(f"Decimate ratio: {args.decimate}")

    results = []
    chatml_lines = []

    for i, f in enumerate(sorted(files)):
        print(f"\n[{i+1}/{len(files)}] Converting: {f.name}")
        try:
            recipe = process_file(str(f), args.max_verts, args.decimals, args.decimate)
            if recipe:
                # Save individual recipe
                out_name = f.stem + ".json"
                out_path = output_dir / out_name
                with open(out_path, "w") as fp:
                    json.dump(recipe, fp, indent=2)

                v = recipe["meta"]["total_vertices"]
                p = recipe["meta"]["parts"]
                t = recipe["tool_count"]
                print(f"  -> {out_path} ({v} verts, {p} parts, {t} tool calls)")
                results.append({"file": f.name, "output": str(out_path),
                               "status": "ok", "verts": v, "parts": p, "tools": t})

                # ChatML format
                if args.chatml:
                    tool_calls_text = []
                    for tc in recipe["tools"]:
                        params_str = json.dumps(tc["params"], separators=(",", ":"))
                        tool_calls_text.append(f'{tc["tool"]}({params_str})')

                    chatml_lines.append(json.dumps({
                        "messages": [
                            {"role": "system", "content": "You are a 3D modeling assistant. Given a description, output MCP tool calls to build the 3D model."},
                            {"role": "user", "content": recipe["prompt"]},
                            {"role": "assistant", "content": "\n".join(tool_calls_text)},
                        ]
                    }))
            else:
                results.append({"file": f.name, "status": "failed"})
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({"file": f.name, "status": "error", "error": str(e)})

    # Write summary
    summary_path = output_dir / "_summary.json"
    ok_results = [r for r in results if r["status"] == "ok"]
    with open(summary_path, "w") as fp:
        json.dump({
            "total_files": len(files),
            "successful": len(ok_results),
            "failed": len(results) - len(ok_results),
            "total_verts": sum(r.get("verts", 0) for r in ok_results),
            "total_tool_calls": sum(r.get("tools", 0) for r in ok_results),
            "results": results,
        }, fp, indent=2)

    # Write ChatML training file
    if args.chatml and chatml_lines:
        chatml_path = output_dir / "training.jsonl"
        with open(chatml_path, "w") as fp:
            for line in chatml_lines:
                fp.write(line + "\n")
        print(f"\nChatML training file: {chatml_path} ({len(chatml_lines)} samples)")

    print(f"\nDone! Summary: {summary_path}")
    print(f"  {len(ok_results)}/{len(files)} files converted")
    if ok_results:
        print(f"  Total vertices: {sum(r.get('verts', 0) for r in ok_results)}")
        print(f"  Total tool calls: {sum(r.get('tools', 0) for r in ok_results)}")


if __name__ == "__main__":
    main()
