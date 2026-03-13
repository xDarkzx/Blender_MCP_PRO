# BlenderMCP Training Data Schema

## Overview
Training data is organized into two types:
1. **Templates** (`templates/`): Analyzed reference models - what a good model looks like
2. **Recipes** (`recipes/`): Step-by-step MCP tool-call sequences to recreate a model

## Template Format (JSON)
Each template captures the full analysis of a reference model imported from BlenderKit or similar.
Used as "ground truth" for what the AI should aim to produce.

## Recipe Format (JSON)
Each recipe is a sequence of MCP tool calls that builds a model from scratch.
This is the actual training data format - pairs of (user_prompt, tool_call_sequence).

## Training Pipeline
1. Import quality model from BlenderKit
2. Run `mesh_analyze_profile` on all parts -> save as Template
3. Write Recipe: step-by-step tool calls to approximate the template
4. Validate: execute recipe in clean scene, compare result to template
5. Log: capture tool calls + screenshots at each step

## File Naming
- `templates/{category}_{name}.json` - e.g. `structure_medieval_well.json`
- `recipes/{category}_{name}.json` - e.g. `structure_medieval_well.json`
