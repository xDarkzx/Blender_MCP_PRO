# BlenderMCP Pro

A secure MCP (Model Context Protocol) server for AI-driven 3D modeling in Blender. Connects any MCP-compatible AI client (Claude, etc.) to Blender through a safe, validated tool interface.

## Architecture

```
AI Client (Claude, etc.)
    |
    | MCP Protocol (stdio)
    v
server/          -- FastMCP server with async TCP client
    |
    | TCP (127.0.0.1:9876, JSON-RPC 2.0, length-prefixed)
    v
addon/           -- Blender addon with TCP server & dispatcher
    |
    v
Blender Python API (bpy)
```

**Key design principle:** Zero `exec()`/`eval()` -- every operation maps to a static handler function with per-parameter input validation. No arbitrary code execution.

## Tools (37)

| Category | Count | Tools |
|----------|-------|-------|
| Scene | 7 | get_info, list_objects, get_object, get_hierarchy, set_unit_system, manage_collection, set_active_object |
| Mesh | 9 | create_primitive, create_custom, edit_geometry, get_geometry, set_smooth_shading, separate, join, set_origin, analyze_profile |
| Object | 8 | set_transform, get_transform, duplicate, delete, parent, unparent, move_to_collection, apply_transform |
| Material | 4 | create, assign, get_info, update |
| Modifier | 3 | add, configure, apply |
| Viewport | 5 | screenshot, set_camera, auto_screenshot, screenshot_cleanup |
| Selection | 1 | set |

### Notable Tools

- **mesh_edit_geometry** -- Chained edit-mode operations (extrude, bevel, loop cut, scale, etc.) with smart selection (by position, normal, Z-range)
- **mesh_analyze_profile** -- Deep mesh analysis for reverse-engineering construction (Z-slice profiles, symmetry detection, material zones, loose parts)
- **mesh_create_custom** -- Create meshes from raw vertex/face data
- **auto_screenshot** -- Automatic viewport captures after every modifying operation

## Setup

### 1. Install the Blender Addon

```bash
# Build the addon zip
python build_addon.py

# Or install directly (finds Blender automatically)
python install_addon.py
```

Then enable "BlenderMCP Pro" in Blender Preferences > Add-ons.

### 2. Install the MCP Server

```bash
pip install -e .
```

### 3. Configure Your AI Client

Add to your MCP client config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "blendermcp": {
      "command": "blendermcp"
    }
  }
}
```

See `claude_desktop_config_example.json` for a full example.

### 4. Connect

1. Open Blender
2. In the addon panel, click "Start Server"
3. Start your MCP client
4. The AI can now control Blender

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

```
addon/              Blender addon (TCP server, handlers, UI)
  handlers/         One module per tool category
  connection.py     TCP server & message framing
  dispatcher.py     Method routing
  validation.py     Input validation
server/             MCP server (FastMCP, async TCP client)
  tools/            One module per tool category
  blender_client.py Async TCP client
  auto_screenshot.py Screenshot management
shared/             Wire protocol, constants, error codes
tests/              pytest unit tests
training/           Training data tools (bulk analyzer, generators)
```

## Training Data Tools

The `training/` directory contains tools for generating and analyzing 3D modeling data:

- **bulk_analyze.py** -- Headless Blender script to batch-analyze FBX/OBJ/GLB files into JSON profiles
- **generate_training_data.py** -- Procedural generator for MCP tool-call training sequences (38 object categories, no LLM needed)
- **fbx_to_recipe.py** -- Converts 3D files into exact `mesh_create_custom` reconstruction recipes

```bash
# Analyze a directory of FBX files
blender --background --python training/bulk_analyze.py -- --input ./models/ --output ./templates/

# Generate 10K training samples
python training/generate_training_data.py --count 10000 --format chatml --split --output ./generated/
```

## License

MIT
