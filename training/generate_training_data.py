"""
Procedural training data generator - NO LLM NEEDED.

Generates thousands of valid MCP tool-call sequences by randomizing
parameterized templates for common 3D objects.

Each generated sample is:
  - prompt: natural language description (auto-generated from params)
  - tools: ordered list of MCP tool calls that WILL work (guaranteed)

Usage:
    python generate_training_data.py --count 100 --output ./generated/
    python generate_training_data.py --count 500 --category table chair barrel
    python generate_training_data.py --count 5000 --output ./generated/ --format chatml
"""

import json
import math
import random
import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple

# ---------------------------------------------------------------------------
# Tool-call builder helpers
# ---------------------------------------------------------------------------

def tool(tool_name: str, **params) -> Dict[str, Any]:
    """Create a tool call dict."""
    # Strip None values
    params = {k: v for k, v in params.items() if v is not None}
    return {"tool": tool_name, "params": params}


def r(val, decimals=3):
    """Round a float."""
    return round(val, decimals)


def rand(lo, hi):
    """Random float in range, rounded."""
    return r(random.uniform(lo, hi))


def pick(*options):
    """Pick a random option."""
    return random.choice(options)


def color_random():
    """Random RGB color."""
    return [r(random.random()), r(random.random()), r(random.random())]


def color_named():
    """Pick a named color with its RGB."""
    colors = {
        "red": [0.8, 0.1, 0.1], "dark red": [0.5, 0.05, 0.05],
        "blue": [0.1, 0.2, 0.8], "dark blue": [0.05, 0.1, 0.5],
        "green": [0.1, 0.6, 0.1], "dark green": [0.05, 0.3, 0.05],
        "yellow": [0.9, 0.8, 0.1], "orange": [0.9, 0.4, 0.05],
        "white": [0.9, 0.9, 0.9], "black": [0.05, 0.05, 0.05],
        "gray": [0.4, 0.4, 0.4], "light gray": [0.7, 0.7, 0.7],
        "brown": [0.4, 0.2, 0.05], "dark brown": [0.25, 0.12, 0.03],
        "tan": [0.7, 0.55, 0.35], "beige": [0.76, 0.7, 0.5],
        "wood brown": [0.45, 0.28, 0.1], "pine": [0.6, 0.45, 0.2],
        "oak": [0.5, 0.35, 0.15], "metal gray": [0.5, 0.5, 0.52],
        "steel": [0.6, 0.6, 0.65], "copper": [0.72, 0.45, 0.2],
        "gold": [0.83, 0.69, 0.22], "brass": [0.71, 0.65, 0.26],
        "stone gray": [0.55, 0.55, 0.5], "brick red": [0.6, 0.2, 0.1],
        "purple": [0.5, 0.1, 0.6], "pink": [0.9, 0.4, 0.5],
        "teal": [0.1, 0.5, 0.5], "cream": [0.95, 0.9, 0.8],
    }
    name = random.choice(list(colors.keys()))
    return name, colors[name]


# ---------------------------------------------------------------------------
# OBJECT GENERATORS
# Each returns (prompt: str, tools: list[dict], tags: list[str])
# ---------------------------------------------------------------------------

def generate_table() -> Tuple[str, List, List]:
    """Generate a table with legs."""
    # Params
    top_w = rand(0.8, 3.0)
    top_d = rand(0.6, 2.0)
    top_h = rand(0.03, 0.08)
    leg_h = rand(0.5, 1.2)
    leg_r = rand(0.02, 0.06)
    leg_shape = pick("CYLINDER", "CUBE")
    n_legs = pick(4, 4, 4, 3, 6)  # mostly 4
    mat_name_top, mat_color_top = color_named()
    mat_name_leg, mat_color_leg = color_named()
    metallic_top = rand(0.0, 0.3)
    roughness_top = rand(0.3, 0.8)
    metallic_leg = rand(0.0, 0.2)
    roughness_leg = rand(0.3, 0.9)
    top_shape = pick("CUBE", "CYLINDER")  # rect or round table

    tools = []

    # Tabletop
    if top_shape == "CUBE":
        tools.append(tool("mesh_create_primitive", type="CUBE", name="Tabletop",
                          size=1, scale=[r(top_w/2), r(top_d/2), r(top_h/2)],
                          location=[0, 0, r(leg_h + top_h/2)]))
        shape_desc = f"{r(top_w)}m x {r(top_d)}m rectangular"
    else:
        tools.append(tool("mesh_create_primitive", type="CYLINDER", name="Tabletop",
                          radius=r(top_w/2), depth=r(top_h), vertices=32,
                          location=[0, 0, r(leg_h + top_h/2)]))
        shape_desc = f"{r(top_w)}m diameter round"

    # Material for top
    tools.append(tool("material_create", name="TableTopMat",
                       base_color=mat_color_top, metallic=r(metallic_top),
                       roughness=r(roughness_top)))
    tools.append(tool("material_assign", object_name="Tabletop",
                       material_name="TableTopMat"))

    # Legs
    inset = 0.85  # legs positioned at 85% of half-width
    if n_legs == 4:
        positions = [
            [-top_w/2 * inset, -top_d/2 * inset],
            [top_w/2 * inset, -top_d/2 * inset],
            [-top_w/2 * inset, top_d/2 * inset],
            [top_w/2 * inset, top_d/2 * inset],
        ]
    elif n_legs == 3:
        positions = [
            [0, -top_d/2 * inset],
            [-top_w/2 * inset, top_d/2 * 0.5],
            [top_w/2 * inset, top_d/2 * 0.5],
        ]
    else:  # 6
        positions = [
            [-top_w/2 * inset, -top_d/2 * inset],
            [0, -top_d/2 * inset],
            [top_w/2 * inset, -top_d/2 * inset],
            [-top_w/2 * inset, top_d/2 * inset],
            [0, top_d/2 * inset],
            [top_w/2 * inset, top_d/2 * inset],
        ]

    for i, (lx, ly) in enumerate(positions):
        leg_name = f"Leg{i+1}"
        if leg_shape == "CYLINDER":
            tools.append(tool("mesh_create_primitive", type="CYLINDER",
                              name=leg_name, radius=r(leg_r), depth=r(leg_h),
                              vertices=12, location=[r(lx), r(ly), r(leg_h/2)]))
        else:
            leg_size = leg_r * 2
            tools.append(tool("mesh_create_primitive", type="CUBE",
                              name=leg_name, size=r(leg_size),
                              scale=[1, 1, r(leg_h / leg_size / 2)],
                              location=[r(lx), r(ly), r(leg_h/2)]))

    # Material for legs
    tools.append(tool("material_create", name="TableLegMat",
                       base_color=mat_color_leg, metallic=r(metallic_leg),
                       roughness=r(roughness_leg)))
    for i in range(n_legs):
        tools.append(tool("material_assign", object_name=f"Leg{i+1}",
                           material_name="TableLegMat"))

    # Prompt
    leg_word = "cylindrical" if leg_shape == "CYLINDER" else "square"
    prompt = (f"Create a {shape_desc} table, {r(leg_h + top_h)}m tall, "
              f"with {n_legs} {leg_word} legs. "
              f"The top should be {mat_name_top} colored and the legs {mat_name_leg}.")

    tags = ["table", "furniture", "interior"]
    return prompt, tools, tags


def generate_chair() -> Tuple[str, List, List]:
    """Generate a chair with seat, back, and legs."""
    seat_w = rand(0.35, 0.55)
    seat_d = rand(0.35, 0.50)
    seat_h = rand(0.02, 0.05)
    leg_h = rand(0.35, 0.55)
    leg_r = rand(0.015, 0.035)
    back_h = rand(0.3, 0.6)
    back_thick = rand(0.02, 0.04)
    mat_name, mat_color = color_named()
    roughness = rand(0.4, 0.9)

    tools = []

    # Seat
    tools.append(tool("mesh_create_primitive", type="CUBE", name="Seat",
                       size=1, scale=[r(seat_w/2), r(seat_d/2), r(seat_h/2)],
                       location=[0, 0, r(leg_h + seat_h/2)]))

    # Back
    tools.append(tool("mesh_create_primitive", type="CUBE", name="Back",
                       size=1, scale=[r(seat_w/2), r(back_thick/2), r(back_h/2)],
                       location=[0, r(-seat_d/2 + back_thick/2), r(leg_h + seat_h + back_h/2)]))

    # 4 legs
    inset = 0.85
    positions = [
        [-seat_w/2 * inset, -seat_d/2 * inset],
        [seat_w/2 * inset, -seat_d/2 * inset],
        [-seat_w/2 * inset, seat_d/2 * inset],
        [seat_w/2 * inset, seat_d/2 * inset],
    ]
    for i, (lx, ly) in enumerate(positions):
        tools.append(tool("mesh_create_primitive", type="CYLINDER",
                          name=f"ChairLeg{i+1}", radius=r(leg_r), depth=r(leg_h),
                          vertices=12, location=[r(lx), r(ly), r(leg_h/2)]))

    # Material
    tools.append(tool("material_create", name="ChairMat",
                       base_color=mat_color, roughness=r(roughness)))
    for name in ["Seat", "Back"] + [f"ChairLeg{i+1}" for i in range(4)]:
        tools.append(tool("material_assign", object_name=name, material_name="ChairMat"))

    total_h = leg_h + seat_h + back_h
    prompt = (f"Create a {mat_name} chair, {r(total_h)}m tall with a "
              f"{r(seat_w)}m wide seat and {r(back_h)}m tall backrest.")

    return prompt, tools, ["chair", "furniture", "interior"]


def generate_barrel() -> Tuple[str, List, List]:
    """Generate a barrel using cylinder with scaled rings."""
    radius = rand(0.2, 0.5)
    height = rand(0.5, 1.2)
    bulge = rand(1.05, 1.25)
    mat_name, mat_color = color_named()
    band_name, band_color = color_named()

    tools = []

    # Main body
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="BarrelBody",
                       radius=r(radius), depth=r(height), vertices=24,
                       location=[0, 0, r(height/2)]))

    # Bulge via edit geometry - scale middle verts
    tools.append(tool("mesh_edit_geometry", object_name="BarrelBody",
                       operation="SCALE",
                       selection={"type": "vert", "z_range": [r(height*0.3), r(height*0.7)]},
                       scale_vector=[r(bulge), r(bulge), 1]))

    # Top band
    tools.append(tool("mesh_create_primitive", type="TORUS", name="TopBand",
                       major_radius=r(radius * 0.98), minor_radius=r(0.01),
                       location=[0, 0, r(height * 0.85)]))

    # Bottom band
    tools.append(tool("mesh_create_primitive", type="TORUS", name="BottomBand",
                       major_radius=r(radius * 0.98), minor_radius=r(0.01),
                       location=[0, 0, r(height * 0.15)]))

    # Materials
    tools.append(tool("material_create", name="BarrelWood",
                       base_color=mat_color, roughness=r(rand(0.6, 0.9))))
    tools.append(tool("material_assign", object_name="BarrelBody",
                       material_name="BarrelWood"))

    tools.append(tool("material_create", name="BarrelBand",
                       base_color=band_color, metallic=r(rand(0.5, 0.9)),
                       roughness=r(rand(0.3, 0.6))))
    for name in ["TopBand", "BottomBand"]:
        tools.append(tool("material_assign", object_name=name,
                           material_name="BarrelBand"))

    tools.append(tool("mesh_set_smooth_shading", object_name="BarrelBody", smooth=True))

    prompt = (f"Create a {mat_name} wooden barrel, {r(height)}m tall with "
              f"{r(radius*2)}m diameter and {band_name} metal bands.")

    return prompt, tools, ["barrel", "container", "medieval", "prop"]


def generate_pillar() -> Tuple[str, List, List]:
    """Generate a column/pillar with base and capital."""
    shaft_r = rand(0.15, 0.4)
    shaft_h = rand(1.5, 4.0)
    base_r = rand(shaft_r * 1.3, shaft_r * 1.8)
    base_h = rand(0.1, 0.3)
    cap_r = rand(shaft_r * 1.2, shaft_r * 1.6)
    cap_h = rand(0.1, 0.25)
    mat_name, mat_color = color_named()
    style = pick("smooth", "fluted")

    tools = []

    # Base
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="PillarBase",
                       radius=r(base_r), depth=r(base_h), vertices=32,
                       location=[0, 0, r(base_h/2)]))

    # Shaft
    segs = 32 if style == "smooth" else 12
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="PillarShaft",
                       radius=r(shaft_r), depth=r(shaft_h), vertices=segs,
                       location=[0, 0, r(base_h + shaft_h/2)]))

    # Capital
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="PillarCapital",
                       radius=r(cap_r), depth=r(cap_h), vertices=32,
                       location=[0, 0, r(base_h + shaft_h + cap_h/2)]))

    # Material
    tools.append(tool("material_create", name="PillarMat",
                       base_color=mat_color, roughness=r(rand(0.5, 0.9))))
    for name in ["PillarBase", "PillarShaft", "PillarCapital"]:
        tools.append(tool("material_assign", object_name=name,
                           material_name="PillarMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name=name, smooth=True))

    total_h = base_h + shaft_h + cap_h
    prompt = (f"Create a {style} {mat_name} pillar, {r(total_h)}m tall with a "
              f"{r(shaft_r*2)}m diameter shaft.")

    return prompt, tools, ["pillar", "column", "architecture", "classical"]


def generate_wall() -> Tuple[str, List, List]:
    """Generate a wall segment, optionally with window or door opening."""
    wall_w = rand(2.0, 6.0)
    wall_h = rand(2.5, 4.0)
    wall_d = rand(0.15, 0.4)
    has_opening = random.random() < 0.5
    mat_name, mat_color = color_named()

    tools = []

    if not has_opening:
        tools.append(tool("mesh_create_primitive", type="CUBE", name="Wall",
                           size=1, scale=[r(wall_w/2), r(wall_d/2), r(wall_h/2)],
                           location=[0, 0, r(wall_h/2)]))
        tools.append(tool("material_create", name="WallMat",
                           base_color=mat_color, roughness=r(rand(0.6, 0.95))))
        tools.append(tool("material_assign", object_name="Wall",
                           material_name="WallMat"))
        prompt = (f"Create a solid {mat_name} wall, {r(wall_w)}m wide and "
                  f"{r(wall_h)}m tall.")
    else:
        opening = pick("door", "window")
        if opening == "door":
            door_w = rand(0.8, 1.2)
            door_h = rand(1.8, 2.4)
            # Wall is three pieces: left, right, top
            left_w = (wall_w - door_w) / 2
            right_w = left_w

            tools.append(tool("mesh_create_primitive", type="CUBE", name="WallLeft",
                               size=1, scale=[r(left_w/2), r(wall_d/2), r(wall_h/2)],
                               location=[r(-wall_w/2 + left_w/2), 0, r(wall_h/2)]))
            tools.append(tool("mesh_create_primitive", type="CUBE", name="WallRight",
                               size=1, scale=[r(right_w/2), r(wall_d/2), r(wall_h/2)],
                               location=[r(wall_w/2 - right_w/2), 0, r(wall_h/2)]))
            top_h = wall_h - door_h
            tools.append(tool("mesh_create_primitive", type="CUBE", name="WallTop",
                               size=1, scale=[r(door_w/2), r(wall_d/2), r(top_h/2)],
                               location=[0, 0, r(door_h + top_h/2)]))

            tools.append(tool("material_create", name="WallMat",
                               base_color=mat_color, roughness=r(rand(0.6, 0.95))))
            for n in ["WallLeft", "WallRight", "WallTop"]:
                tools.append(tool("material_assign", object_name=n,
                                   material_name="WallMat"))

            prompt = (f"Create a {mat_name} wall, {r(wall_w)}m wide and "
                      f"{r(wall_h)}m tall, with a {r(door_w)}m x {r(door_h)}m door opening.")
        else:
            win_w = rand(0.6, 1.5)
            win_h = rand(0.6, 1.2)
            win_z = rand(0.8, 1.5)
            # Wall split: left, right, below window, above window
            left_w = (wall_w - win_w) / 2

            tools.append(tool("mesh_create_primitive", type="CUBE", name="WallLeft",
                               size=1, scale=[r(left_w/2), r(wall_d/2), r(wall_h/2)],
                               location=[r(-wall_w/2 + left_w/2), 0, r(wall_h/2)]))
            tools.append(tool("mesh_create_primitive", type="CUBE", name="WallRight",
                               size=1, scale=[r(left_w/2), r(wall_d/2), r(wall_h/2)],
                               location=[r(wall_w/2 - left_w/2), 0, r(wall_h/2)]))
            tools.append(tool("mesh_create_primitive", type="CUBE", name="WallBelow",
                               size=1, scale=[r(win_w/2), r(wall_d/2), r(win_z/2)],
                               location=[0, 0, r(win_z/2)]))
            above_h = wall_h - win_z - win_h
            tools.append(tool("mesh_create_primitive", type="CUBE", name="WallAbove",
                               size=1, scale=[r(win_w/2), r(wall_d/2), r(above_h/2)],
                               location=[0, 0, r(win_z + win_h + above_h/2)]))

            tools.append(tool("material_create", name="WallMat",
                               base_color=mat_color, roughness=r(rand(0.6, 0.95))))
            for n in ["WallLeft", "WallRight", "WallBelow", "WallAbove"]:
                tools.append(tool("material_assign", object_name=n,
                                   material_name="WallMat"))

            prompt = (f"Create a {mat_name} wall, {r(wall_w)}m wide and "
                      f"{r(wall_h)}m tall, with a {r(win_w)}m x {r(win_h)}m window "
                      f"at {r(win_z)}m height.")

    tags = ["wall", "architecture", "building"]
    if has_opening:
        tags.append(opening)
    return prompt, tools, tags


def generate_shelf() -> Tuple[str, List, List]:
    """Generate a bookshelf/shelf unit."""
    width = rand(0.6, 2.0)
    depth = rand(0.2, 0.45)
    height = rand(0.8, 2.5)
    n_shelves = random.randint(2, 6)
    thick = rand(0.015, 0.03)
    side_thick = rand(0.02, 0.04)
    mat_name, mat_color = color_named()

    tools = []

    # Left side
    tools.append(tool("mesh_create_primitive", type="CUBE", name="ShelfLeft",
                       size=1, scale=[r(side_thick/2), r(depth/2), r(height/2)],
                       location=[r(-width/2), 0, r(height/2)]))
    # Right side
    tools.append(tool("mesh_create_primitive", type="CUBE", name="ShelfRight",
                       size=1, scale=[r(side_thick/2), r(depth/2), r(height/2)],
                       location=[r(width/2), 0, r(height/2)]))

    # Shelves (evenly spaced)
    inner_w = width - side_thick
    for i in range(n_shelves):
        z = (height / (n_shelves - 1)) * i if n_shelves > 1 else height / 2
        tools.append(tool("mesh_create_primitive", type="CUBE",
                           name=f"Shelf{i+1}", size=1,
                           scale=[r(inner_w/2), r(depth/2), r(thick/2)],
                           location=[0, 0, r(z + thick/2)]))

    # Optional back panel
    if random.random() < 0.6:
        tools.append(tool("mesh_create_primitive", type="CUBE", name="ShelfBack",
                           size=1, scale=[r(width/2), r(0.005), r(height/2)],
                           location=[0, r(-depth/2 + 0.005), r(height/2)]))

    # Material
    tools.append(tool("material_create", name="ShelfMat",
                       base_color=mat_color, roughness=r(rand(0.5, 0.9))))
    all_parts = ["ShelfLeft", "ShelfRight"] + [f"Shelf{i+1}" for i in range(n_shelves)]
    if random.random() < 0.6:
        all_parts.append("ShelfBack")
    for name in all_parts:
        tools.append(tool("material_assign", object_name=name, material_name="ShelfMat"))

    prompt = (f"Create a {mat_name} shelf unit, {r(width)}m wide, {r(height)}m tall "
              f"with {n_shelves} shelves.")

    return prompt, tools, ["shelf", "bookshelf", "furniture", "interior", "storage"]


def generate_lamp() -> Tuple[str, List, List]:
    """Generate a standing lamp with base, pole, and shade."""
    base_r = rand(0.12, 0.25)
    base_h = rand(0.02, 0.05)
    pole_r = rand(0.01, 0.03)
    pole_h = rand(0.8, 1.8)
    shade_r_bottom = rand(0.12, 0.25)
    shade_r_top = rand(0.03, shade_r_bottom * 0.6)
    shade_h = rand(0.12, 0.25)
    mat_name_base, mat_color_base = color_named()
    mat_name_shade, mat_color_shade = color_named()

    tools = []

    # Base
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="LampBase",
                       radius=r(base_r), depth=r(base_h), vertices=32,
                       location=[0, 0, r(base_h/2)]))

    # Pole
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="LampPole",
                       radius=r(pole_r), depth=r(pole_h), vertices=12,
                       location=[0, 0, r(base_h + pole_h/2)]))

    # Shade (cone/truncated cone)
    tools.append(tool("mesh_create_primitive", type="CONE", name="LampShade",
                       radius1=r(shade_r_bottom), radius2=r(shade_r_top),
                       depth=r(shade_h), vertices=32,
                       location=[0, 0, r(base_h + pole_h + shade_h/2)]))

    # Materials
    tools.append(tool("material_create", name="LampBaseMat",
                       base_color=mat_color_base, metallic=r(rand(0.3, 0.8)),
                       roughness=r(rand(0.3, 0.6))))
    tools.append(tool("material_assign", object_name="LampBase",
                       material_name="LampBaseMat"))
    tools.append(tool("material_assign", object_name="LampPole",
                       material_name="LampBaseMat"))

    tools.append(tool("material_create", name="LampShadeMat",
                       base_color=mat_color_shade, roughness=r(rand(0.4, 0.8))))
    tools.append(tool("material_assign", object_name="LampShade",
                       material_name="LampShadeMat"))

    tools.append(tool("mesh_set_smooth_shading", object_name="LampBase", smooth=True))
    tools.append(tool("mesh_set_smooth_shading", object_name="LampPole", smooth=True))
    tools.append(tool("mesh_set_smooth_shading", object_name="LampShade", smooth=True))

    total_h = base_h + pole_h + shade_h
    prompt = (f"Create a standing lamp, {r(total_h)}m tall, with a {mat_name_base} "
              f"metal base and a {mat_name_shade} shade.")

    return prompt, tools, ["lamp", "light", "furniture", "interior"]


def generate_fence() -> Tuple[str, List, List]:
    """Generate a fence section with posts and rails."""
    n_posts = random.randint(3, 8)
    spacing = rand(0.8, 2.0)
    post_r = rand(0.03, 0.06)
    post_h = rand(0.8, 1.5)
    rail_h_pct = [0.3, 0.7] if random.random() < 0.5 else [0.25, 0.5, 0.75]
    rail_thick = rand(0.02, 0.04)
    mat_name, mat_color = color_named()

    tools = []
    total_w = spacing * (n_posts - 1)

    # Posts
    for i in range(n_posts):
        x = -total_w / 2 + spacing * i
        tools.append(tool("mesh_create_primitive", type="CYLINDER",
                          name=f"Post{i+1}", radius=r(post_r), depth=r(post_h),
                          vertices=8, location=[r(x), 0, r(post_h/2)]))

    # Rails
    for j, pct in enumerate(rail_h_pct):
        z = post_h * pct
        tools.append(tool("mesh_create_primitive", type="CUBE",
                          name=f"Rail{j+1}", size=1,
                          scale=[r(total_w/2), r(rail_thick/2), r(rail_thick/2)],
                          location=[0, 0, r(z)]))

    # Material
    tools.append(tool("material_create", name="FenceMat",
                       base_color=mat_color, roughness=r(rand(0.5, 0.9))))
    all_parts = [f"Post{i+1}" for i in range(n_posts)] + [f"Rail{j+1}" for j in range(len(rail_h_pct))]
    for name in all_parts:
        tools.append(tool("material_assign", object_name=name, material_name="FenceMat"))

    n_rails = len(rail_h_pct)
    prompt = (f"Create a {mat_name} fence, {r(total_w)}m long and {r(post_h)}m tall, "
              f"with {n_posts} posts and {n_rails} horizontal rails.")

    return prompt, tools, ["fence", "exterior", "barrier"]


def generate_crate() -> Tuple[str, List, List]:
    """Generate a simple crate/box."""
    w = rand(0.3, 1.5)
    h = rand(0.3, 1.2)
    d = rand(0.3, 1.2)
    mat_name, mat_color = color_named()
    has_lid = random.random() < 0.4

    tools = []

    tools.append(tool("mesh_create_primitive", type="CUBE", name="Crate",
                       size=1, scale=[r(w/2), r(d/2), r(h/2)],
                       location=[0, 0, r(h/2)]))

    if has_lid:
        lid_h = rand(0.02, 0.05)
        tools.append(tool("mesh_create_primitive", type="CUBE", name="CrateLid",
                           size=1, scale=[r(w/2 * 1.05), r(d/2 * 1.05), r(lid_h/2)],
                           location=[0, 0, r(h + lid_h/2)]))

    # Edge bevel for a nicer look
    tools.append(tool("modifier_add", object_name="Crate", type="BEVEL",
                       properties={"width": r(rand(0.005, 0.02)), "segments": 2}))

    tools.append(tool("material_create", name="CrateMat",
                       base_color=mat_color, roughness=r(rand(0.6, 0.95))))
    tools.append(tool("material_assign", object_name="Crate", material_name="CrateMat"))
    if has_lid:
        tools.append(tool("material_assign", object_name="CrateLid",
                           material_name="CrateMat"))

    lid_desc = " with a lid" if has_lid else ""
    prompt = (f"Create a {mat_name} crate{lid_desc}, {r(w)}m x {r(d)}m x {r(h)}m.")

    return prompt, tools, ["crate", "box", "container", "prop"]


def generate_staircase() -> Tuple[str, List, List]:
    """Generate a straight staircase."""
    n_steps = random.randint(4, 12)
    step_w = rand(0.8, 1.5)
    step_d = rand(0.2, 0.35)
    step_h = rand(0.15, 0.22)
    mat_name, mat_color = color_named()

    tools = []

    for i in range(n_steps):
        tools.append(tool("mesh_create_primitive", type="CUBE",
                          name=f"Step{i+1}", size=1,
                          scale=[r(step_w/2), r(step_d/2), r(step_h/2)],
                          location=[0, r(step_d * i), r(step_h * (i + 0.5))]))

    tools.append(tool("material_create", name="StairMat",
                       base_color=mat_color, roughness=r(rand(0.5, 0.9))))
    for i in range(n_steps):
        tools.append(tool("material_assign", object_name=f"Step{i+1}",
                           material_name="StairMat"))

    total_h = step_h * n_steps
    total_d = step_d * n_steps
    prompt = (f"Create a {mat_name} staircase with {n_steps} steps, "
              f"{r(step_w)}m wide, rising {r(total_h)}m over {r(total_d)}m depth.")

    return prompt, tools, ["stairs", "staircase", "architecture"]


def generate_arch() -> Tuple[str, List, List]:
    """Generate an arch with two pillars and a curved top."""
    pillar_r = rand(0.15, 0.35)
    pillar_h = rand(2.0, 3.5)
    gap = rand(1.5, 3.0)
    mat_name, mat_color = color_named()

    tools = []

    # Left pillar
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="ArchLeft",
                       radius=r(pillar_r), depth=r(pillar_h), vertices=24,
                       location=[r(-gap/2), 0, r(pillar_h/2)]))
    # Right pillar
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="ArchRight",
                       radius=r(pillar_r), depth=r(pillar_h), vertices=24,
                       location=[r(gap/2), 0, r(pillar_h/2)]))
    # Arch top (torus half)
    arch_r = gap / 2
    tools.append(tool("mesh_create_primitive", type="TORUS", name="ArchTop",
                       major_radius=r(arch_r), minor_radius=r(pillar_r),
                       major_segments=24, minor_segments=12,
                       location=[0, 0, r(pillar_h)]))

    # Material
    tools.append(tool("material_create", name="ArchMat",
                       base_color=mat_color, roughness=r(rand(0.5, 0.9))))
    for name in ["ArchLeft", "ArchRight", "ArchTop"]:
        tools.append(tool("material_assign", object_name=name, material_name="ArchMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name=name, smooth=True))

    total_h = pillar_h + arch_r
    prompt = (f"Create a {mat_name} archway, {r(gap)}m wide and ~{r(total_h)}m tall, "
              f"with cylindrical pillars and a rounded top.")

    return prompt, tools, ["arch", "archway", "architecture", "medieval"]


def generate_platform() -> Tuple[str, List, List]:
    """Generate a raised platform/stage."""
    w = rand(2.0, 6.0)
    d = rand(2.0, 5.0)
    h = rand(0.2, 1.0)
    has_steps = random.random() < 0.5
    mat_name, mat_color = color_named()

    tools = []

    tools.append(tool("mesh_create_primitive", type="CUBE", name="Platform",
                       size=1, scale=[r(w/2), r(d/2), r(h/2)],
                       location=[0, 0, r(h/2)]))

    if has_steps:
        n_steps = max(2, int(h / 0.2))
        step_d = rand(0.25, 0.4)
        step_h = h / n_steps
        for i in range(n_steps):
            tools.append(tool("mesh_create_primitive", type="CUBE",
                              name=f"PlatformStep{i+1}", size=1,
                              scale=[r(w/2), r(step_d/2), r(step_h/2)],
                              location=[0, r(d/2 + step_d * (i + 0.5)), r(step_h * (i + 0.5))]))

    tools.append(tool("material_create", name="PlatformMat",
                       base_color=mat_color, roughness=r(rand(0.5, 0.9))))
    tools.append(tool("material_assign", object_name="Platform",
                       material_name="PlatformMat"))
    if has_steps:
        for i in range(n_steps):
            tools.append(tool("material_assign", object_name=f"PlatformStep{i+1}",
                               material_name="PlatformMat"))

    step_desc = f" with {n_steps} steps" if has_steps else ""
    prompt = (f"Create a {mat_name} platform, {r(w)}m x {r(d)}m, "
              f"{r(h)}m high{step_desc}.")

    return prompt, tools, ["platform", "stage", "architecture"]


def generate_tree_simple() -> Tuple[str, List, List]:
    """Generate a simple stylized tree (trunk + foliage sphere/cone)."""
    trunk_r = rand(0.08, 0.2)
    trunk_h = rand(1.0, 3.0)
    foliage_type = pick("sphere", "cone")
    foliage_r = rand(0.5, 1.5)
    foliage_h = rand(1.0, 2.5) if foliage_type == "cone" else foliage_r * 2
    trunk_name, trunk_color = color_named()
    foliage_name, foliage_color = color_named()
    # Bias foliage to greens
    if random.random() < 0.7:
        foliage_name = pick("green", "dark green")
        foliage_color = {"green": [0.1, 0.6, 0.1], "dark green": [0.05, 0.3, 0.05]}[foliage_name]
    if random.random() < 0.7:
        trunk_name = pick("brown", "dark brown", "wood brown")
        trunk_color = {"brown": [0.4, 0.2, 0.05], "dark brown": [0.25, 0.12, 0.03],
                       "wood brown": [0.45, 0.28, 0.1]}[trunk_name]

    tools = []

    # Trunk
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="Trunk",
                       radius=r(trunk_r), depth=r(trunk_h), vertices=12,
                       location=[0, 0, r(trunk_h/2)]))

    # Foliage
    if foliage_type == "sphere":
        tools.append(tool("mesh_create_primitive", type="SPHERE", name="Foliage",
                           radius=r(foliage_r), segments=16, ring_count=12,
                           location=[0, 0, r(trunk_h + foliage_r * 0.7)]))
    else:
        tools.append(tool("mesh_create_primitive", type="CONE", name="Foliage",
                           radius1=r(foliage_r), radius2=0, depth=r(foliage_h),
                           vertices=16,
                           location=[0, 0, r(trunk_h + foliage_h/2)]))

    # Materials
    tools.append(tool("material_create", name="TrunkMat",
                       base_color=trunk_color, roughness=r(rand(0.7, 0.95))))
    tools.append(tool("material_assign", object_name="Trunk", material_name="TrunkMat"))

    tools.append(tool("material_create", name="FoliageMat",
                       base_color=foliage_color, roughness=r(rand(0.6, 0.9))))
    tools.append(tool("material_assign", object_name="Foliage",
                       material_name="FoliageMat"))

    tools.append(tool("mesh_set_smooth_shading", object_name="Foliage", smooth=True))

    shape_word = "round" if foliage_type == "sphere" else "conical"
    total_h = trunk_h + (foliage_r * 1.4 if foliage_type == "sphere" else foliage_h)
    prompt = (f"Create a simple stylized tree, {r(total_h)}m tall, with a "
              f"{trunk_name} trunk and {shape_word} {foliage_name} foliage.")

    return prompt, tools, ["tree", "nature", "vegetation", "stylized"]


def generate_bench() -> Tuple[str, List, List]:
    """Generate a park bench."""
    seat_w = rand(1.2, 2.5)
    seat_d = rand(0.35, 0.5)
    seat_h = rand(0.03, 0.05)
    leg_h = rand(0.35, 0.55)
    back_h = rand(0.3, 0.5)
    back_thick = rand(0.02, 0.04)
    arm_h = rand(0.15, 0.25)
    has_arms = random.random() < 0.5
    mat_name_seat, color_seat = color_named()
    mat_name_frame, color_frame = color_named()

    tools = []

    # Seat plank
    tools.append(tool("mesh_create_primitive", type="CUBE", name="BenchSeat",
                       size=1, scale=[r(seat_w/2), r(seat_d/2), r(seat_h/2)],
                       location=[0, 0, r(leg_h + seat_h/2)]))

    # Back
    tools.append(tool("mesh_create_primitive", type="CUBE", name="BenchBack",
                       size=1, scale=[r(seat_w/2), r(back_thick/2), r(back_h/2)],
                       location=[0, r(-seat_d/2 + back_thick/2),
                                 r(leg_h + seat_h + back_h/2)]))

    # Legs (2 side frames)
    leg_thick = rand(0.03, 0.05)
    for i, x in enumerate([r(-seat_w * 0.4), r(seat_w * 0.4)]):
        # Front leg
        tools.append(tool("mesh_create_primitive", type="CUBE",
                          name=f"FrontLeg{i+1}", size=1,
                          scale=[r(leg_thick/2), r(leg_thick/2), r(leg_h/2)],
                          location=[x, r(seat_d/2 * 0.8), r(leg_h/2)]))
        # Back leg (taller for backrest support)
        total_back_h = leg_h + seat_h + back_h
        tools.append(tool("mesh_create_primitive", type="CUBE",
                          name=f"BackLeg{i+1}", size=1,
                          scale=[r(leg_thick/2), r(leg_thick/2), r(total_back_h/2)],
                          location=[x, r(-seat_d/2 * 0.8), r(total_back_h/2)]))

    # Arms
    if has_arms:
        for i, x in enumerate([r(-seat_w/2), r(seat_w/2)]):
            tools.append(tool("mesh_create_primitive", type="CUBE",
                              name=f"Arm{i+1}", size=1,
                              scale=[r(leg_thick/2), r(seat_d/2), r(leg_thick/2)],
                              location=[x, 0, r(leg_h + seat_h + arm_h)]))

    # Materials
    tools.append(tool("material_create", name="BenchSeatMat",
                       base_color=color_seat, roughness=r(rand(0.6, 0.9))))
    tools.append(tool("material_assign", object_name="BenchSeat",
                       material_name="BenchSeatMat"))
    tools.append(tool("material_assign", object_name="BenchBack",
                       material_name="BenchSeatMat"))

    tools.append(tool("material_create", name="BenchFrameMat",
                       base_color=color_frame, metallic=r(rand(0.2, 0.7)),
                       roughness=r(rand(0.4, 0.7))))
    frame_parts = [f"FrontLeg{i+1}" for i in range(2)] + [f"BackLeg{i+1}" for i in range(2)]
    if has_arms:
        frame_parts += [f"Arm{i+1}" for i in range(2)]
    for name in frame_parts:
        tools.append(tool("material_assign", object_name=name,
                           material_name="BenchFrameMat"))

    arm_desc = " with armrests" if has_arms else ""
    prompt = (f"Create a park bench{arm_desc}, {r(seat_w)}m wide, "
              f"with {mat_name_seat} seat and {mat_name_frame} frame.")

    return prompt, tools, ["bench", "furniture", "exterior", "park"]


def generate_tower() -> Tuple[str, List, List]:
    """Generate a simple tower/turret."""
    base_r = rand(0.8, 2.0)
    height = rand(3.0, 8.0)
    n_sections = random.randint(2, 4)
    taper = rand(0.7, 0.95)
    has_roof = random.random() < 0.7
    mat_name, mat_color = color_named()
    roof_name, roof_color = color_named()

    tools = []
    current_z = 0
    current_r = base_r
    section_h = height / n_sections

    for i in range(n_sections):
        next_r = current_r * taper
        tools.append(tool("mesh_create_primitive", type="CONE",
                          name=f"TowerSection{i+1}",
                          radius1=r(current_r), radius2=r(next_r),
                          depth=r(section_h), vertices=24,
                          location=[0, 0, r(current_z + section_h/2)]))
        current_z += section_h
        current_r = next_r

    if has_roof:
        roof_h = rand(1.0, 2.5)
        tools.append(tool("mesh_create_primitive", type="CONE", name="TowerRoof",
                           radius1=r(current_r * 1.1), radius2=0,
                           depth=r(roof_h), vertices=24,
                           location=[0, 0, r(current_z + roof_h/2)]))

    # Materials
    tools.append(tool("material_create", name="TowerMat",
                       base_color=mat_color, roughness=r(rand(0.6, 0.95))))
    for i in range(n_sections):
        tools.append(tool("material_assign", object_name=f"TowerSection{i+1}",
                           material_name="TowerMat"))
        tools.append(tool("mesh_set_smooth_shading",
                           object_name=f"TowerSection{i+1}", smooth=True))

    if has_roof:
        tools.append(tool("material_create", name="TowerRoofMat",
                           base_color=roof_color, roughness=r(rand(0.5, 0.8))))
        tools.append(tool("material_assign", object_name="TowerRoof",
                           material_name="TowerRoofMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name="TowerRoof", smooth=True))

    roof_desc = f" with a {roof_name} pointed roof" if has_roof else ""
    prompt = (f"Create a {mat_name} tower, {r(height)}m tall with {n_sections} "
              f"sections tapering upward{roof_desc}.")

    return prompt, tools, ["tower", "turret", "architecture", "medieval"]


def generate_well() -> Tuple[str, List, List]:
    """Generate a simple well with stone base and roof."""
    base_r = rand(0.4, 0.8)
    base_h = rand(0.5, 1.0)
    wall_thick = rand(0.08, 0.15)
    post_h = rand(1.0, 1.8)
    post_r = rand(0.03, 0.06)
    has_roof = random.random() < 0.7
    mat_name, mat_color = color_named()

    tools = []

    # Well cylinder (hollow - outer ring)
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="WellWall",
                       radius=r(base_r), depth=r(base_h), vertices=24,
                       location=[0, 0, r(base_h/2)]))
    # Add solidify to make it hollow
    tools.append(tool("modifier_add", object_name="WellWall", type="SOLIDIFY",
                       properties={"thickness": r(wall_thick)}))

    if has_roof:
        # Two posts
        tools.append(tool("mesh_create_primitive", type="CYLINDER", name="WellPost1",
                           radius=r(post_r), depth=r(post_h), vertices=8,
                           location=[r(-base_r * 0.7), 0, r(base_h + post_h/2)]))
        tools.append(tool("mesh_create_primitive", type="CYLINDER", name="WellPost2",
                           radius=r(post_r), depth=r(post_h), vertices=8,
                           location=[r(base_r * 0.7), 0, r(base_h + post_h/2)]))

        # Roof (two-sided)
        roof_w = base_r * 2.2
        roof_d = base_r * 1.5
        roof_h = rand(0.3, 0.6)
        roof_z = base_h + post_h
        tools.append(tool("mesh_create_primitive", type="CUBE", name="WellRoofLeft",
                           size=1, scale=[r(roof_w/2), r(roof_d/2), r(0.02)],
                           rotation=[r(math.radians(20)), 0, 0],
                           location=[0, r(-roof_d/4), r(roof_z + roof_h * 0.3)]))
        tools.append(tool("mesh_create_primitive", type="CUBE", name="WellRoofRight",
                           size=1, scale=[r(roof_w/2), r(roof_d/2), r(0.02)],
                           rotation=[r(math.radians(-20)), 0, 0],
                           location=[0, r(roof_d/4), r(roof_z + roof_h * 0.3)]))

    # Material
    tools.append(tool("material_create", name="WellMat",
                       base_color=mat_color, roughness=r(rand(0.6, 0.95))))
    parts = ["WellWall"]
    if has_roof:
        parts += ["WellPost1", "WellPost2", "WellRoofLeft", "WellRoofRight"]
    for name in parts:
        tools.append(tool("material_assign", object_name=name, material_name="WellMat"))

    tools.append(tool("mesh_set_smooth_shading", object_name="WellWall", smooth=True))

    roof_desc = " with a wooden roof" if has_roof else ""
    prompt = (f"Create a {mat_name} stone well{roof_desc}, {r(base_r*2)}m diameter "
              f"and {r(base_h)}m wall height.")

    return prompt, tools, ["well", "medieval", "architecture", "prop"]


def generate_window_frame() -> Tuple[str, List, List]:
    """Generate a window frame."""
    w = rand(0.6, 1.5)
    h = rand(0.8, 1.8)
    frame_thick = rand(0.03, 0.06)
    frame_depth = rand(0.03, 0.06)
    has_cross = random.random() < 0.5
    mat_name, mat_color = color_named()

    tools = []

    # Four frame pieces
    # Top
    tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameTop",
                       size=1, scale=[r(w/2), r(frame_depth/2), r(frame_thick/2)],
                       location=[0, 0, r(h)]))
    # Bottom
    tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameBottom",
                       size=1, scale=[r(w/2), r(frame_depth/2), r(frame_thick/2)],
                       location=[0, 0, 0]))
    # Left
    tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameLeft",
                       size=1, scale=[r(frame_thick/2), r(frame_depth/2), r(h/2)],
                       location=[r(-w/2), 0, r(h/2)]))
    # Right
    tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameRight",
                       size=1, scale=[r(frame_thick/2), r(frame_depth/2), r(h/2)],
                       location=[r(w/2), 0, r(h/2)]))

    parts = ["FrameTop", "FrameBottom", "FrameLeft", "FrameRight"]

    if has_cross:
        # Horizontal divider
        tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameCrossH",
                           size=1, scale=[r(w/2), r(frame_depth/2), r(frame_thick/4)],
                           location=[0, 0, r(h/2)]))
        # Vertical divider
        tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameCrossV",
                           size=1, scale=[r(frame_thick/4), r(frame_depth/2), r(h/2)],
                           location=[0, 0, r(h/2)]))
        parts += ["FrameCrossH", "FrameCrossV"]

    tools.append(tool("material_create", name="FrameMat",
                       base_color=mat_color, roughness=r(rand(0.4, 0.8))))
    for name in parts:
        tools.append(tool("material_assign", object_name=name, material_name="FrameMat"))

    cross_desc = " with cross dividers" if has_cross else ""
    prompt = (f"Create a {mat_name} window frame{cross_desc}, "
              f"{r(w)}m x {r(h)}m.")

    return prompt, tools, ["window", "frame", "architecture", "building"]


def generate_candlestick() -> Tuple[str, List, List]:
    """Candlestick - cylinder base, thin pole, torus dish, small cylinder candle."""
    base_r = rand(0.04, 0.08)
    base_h = rand(0.01, 0.03)
    pole_r = rand(0.005, 0.015)
    pole_h = rand(0.1, 0.25)
    dish_r = rand(0.025, 0.05)
    candle_r = rand(0.008, 0.02)
    candle_h = rand(0.06, 0.15)
    mat_name, mat_color = color_named()

    tools = []
    z = 0

    # Base
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="CandleBase",
                       radius=r(base_r), depth=r(base_h), vertices=24,
                       location=[0, 0, r(base_h/2)]))
    z += base_h

    # Pole
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="CandlePole",
                       radius=r(pole_r), depth=r(pole_h), vertices=12,
                       location=[0, 0, r(z + pole_h/2)]))
    z += pole_h

    # Dish
    tools.append(tool("mesh_create_primitive", type="TORUS", name="CandleDish",
                       major_radius=r(dish_r), minor_radius=r(0.005),
                       location=[0, 0, r(z)]))

    # Candle
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="Candle",
                       radius=r(candle_r), depth=r(candle_h), vertices=12,
                       location=[0, 0, r(z + candle_h/2)]))

    # Materials
    tools.append(tool("material_create", name="CandlestickMat",
                       base_color=mat_color, metallic=r(rand(0.5, 0.9)),
                       roughness=r(rand(0.2, 0.5))))
    for n in ["CandleBase", "CandlePole", "CandleDish"]:
        tools.append(tool("material_assign", object_name=n, material_name="CandlestickMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name=n, smooth=True))

    tools.append(tool("material_create", name="CandleWax",
                       base_color=[0.95, 0.92, 0.82], roughness=r(rand(0.7, 0.95))))
    tools.append(tool("material_assign", object_name="Candle", material_name="CandleWax"))

    prompt = (f"Create a {mat_name} candlestick holder with a candle, "
              f"{r(z + candle_h)}m tall.")
    return prompt, tools, ["candlestick", "prop", "interior", "medieval"]


def generate_mushroom() -> Tuple[str, List, List]:
    """Stylized mushroom - cylinder stem + flattened sphere cap."""
    stem_r = rand(0.03, 0.08)
    stem_h = rand(0.08, 0.2)
    cap_r = rand(0.06, 0.18)
    cap_squish = rand(0.3, 0.6)  # vertical scale for flattening
    stem_name, stem_color = color_named()
    cap_name, cap_color = color_named()
    # Bias colors
    if random.random() < 0.6:
        stem_color = [0.9, 0.88, 0.78]
        stem_name = "cream"
    if random.random() < 0.5:
        cap_name = pick("red", "brown", "orange")
        cap_color = {"red": [0.8, 0.15, 0.1], "brown": [0.45, 0.25, 0.1],
                     "orange": [0.85, 0.4, 0.08]}[cap_name]

    tools = []

    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="MushroomStem",
                       radius=r(stem_r), depth=r(stem_h), vertices=12,
                       location=[0, 0, r(stem_h/2)]))

    tools.append(tool("mesh_create_primitive", type="SPHERE", name="MushroomCap",
                       radius=r(cap_r), segments=16, ring_count=12,
                       scale=[1, 1, r(cap_squish)],
                       location=[0, 0, r(stem_h + cap_r * cap_squish * 0.3)]))

    tools.append(tool("material_create", name="StemMat",
                       base_color=stem_color, roughness=r(rand(0.7, 0.95))))
    tools.append(tool("material_assign", object_name="MushroomStem", material_name="StemMat"))

    tools.append(tool("material_create", name="CapMat",
                       base_color=cap_color, roughness=r(rand(0.5, 0.8))))
    tools.append(tool("material_assign", object_name="MushroomCap", material_name="CapMat"))

    tools.append(tool("mesh_set_smooth_shading", object_name="MushroomStem", smooth=True))
    tools.append(tool("mesh_set_smooth_shading", object_name="MushroomCap", smooth=True))

    prompt = (f"Create a stylized mushroom with a {stem_name} stem and "
              f"{cap_name} cap, {r(stem_h + cap_r * cap_squish)}m tall.")
    return prompt, tools, ["mushroom", "nature", "stylized", "prop"]


def generate_cup() -> Tuple[str, List, List]:
    """Cup/mug - cylinder with solidify (hollow) + optional handle torus."""
    radius = rand(0.03, 0.06)
    height = rand(0.06, 0.12)
    wall_thick = rand(0.002, 0.005)
    has_handle = random.random() < 0.7
    mat_name, mat_color = color_named()

    tools = []

    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="Cup",
                       radius=r(radius), depth=r(height), vertices=24,
                       location=[0, 0, r(height/2)]))

    tools.append(tool("modifier_add", object_name="Cup", type="SOLIDIFY",
                       properties={"thickness": r(wall_thick), "offset": -1}))

    if has_handle:
        handle_r = rand(radius * 0.4, radius * 0.6)
        tools.append(tool("mesh_create_primitive", type="TORUS", name="CupHandle",
                           major_radius=r(handle_r), minor_radius=r(0.003),
                           major_segments=16, minor_segments=8,
                           scale=[0.6, 1, 1],
                           location=[r(radius + handle_r * 0.5), 0, r(height * 0.5)]))

    tools.append(tool("material_create", name="CupMat",
                       base_color=mat_color, roughness=r(rand(0.3, 0.7))))
    tools.append(tool("material_assign", object_name="Cup", material_name="CupMat"))
    if has_handle:
        tools.append(tool("material_assign", object_name="CupHandle", material_name="CupMat"))

    tools.append(tool("mesh_set_smooth_shading", object_name="Cup", smooth=True))

    handle_desc = " with a handle" if has_handle else ""
    prompt = (f"Create a {mat_name} cup{handle_desc}, {r(height*100)}cm tall, "
              f"{r(radius*200)}cm diameter.")
    return prompt, tools, ["cup", "mug", "tableware", "interior", "prop"]


def generate_bottle() -> Tuple[str, List, List]:
    """Bottle - cylinder body, tapered neck via cone, small cylinder cap."""
    body_r = rand(0.03, 0.06)
    body_h = rand(0.1, 0.2)
    neck_r = rand(body_r * 0.3, body_r * 0.5)
    neck_h = rand(0.03, 0.08)
    cap_h = rand(0.01, 0.02)
    mat_name, mat_color = color_named()
    # Bias to glass-like colors
    if random.random() < 0.5:
        mat_name = pick("green", "dark green", "brown", "dark blue")
        mat_color = {"green": [0.1, 0.5, 0.15], "dark green": [0.05, 0.3, 0.08],
                     "brown": [0.35, 0.2, 0.05], "dark blue": [0.05, 0.1, 0.4]}[mat_name]

    tools = []
    z = 0

    # Body
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="BottleBody",
                       radius=r(body_r), depth=r(body_h), vertices=24,
                       location=[0, 0, r(body_h/2)]))
    z += body_h

    # Shoulder (cone transition)
    shoulder_h = rand(0.02, 0.04)
    tools.append(tool("mesh_create_primitive", type="CONE", name="BottleShoulder",
                       radius1=r(body_r), radius2=r(neck_r), depth=r(shoulder_h),
                       vertices=24, location=[0, 0, r(z + shoulder_h/2)]))
    z += shoulder_h

    # Neck
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="BottleNeck",
                       radius=r(neck_r), depth=r(neck_h), vertices=24,
                       location=[0, 0, r(z + neck_h/2)]))
    z += neck_h

    # Cap
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="BottleCap",
                       radius=r(neck_r * 1.15), depth=r(cap_h), vertices=24,
                       location=[0, 0, r(z + cap_h/2)]))

    # Material
    tools.append(tool("material_create", name="BottleMat",
                       base_color=mat_color, roughness=r(rand(0.1, 0.4)),
                       metallic=r(rand(0.0, 0.1))))
    for n in ["BottleBody", "BottleShoulder", "BottleNeck"]:
        tools.append(tool("material_assign", object_name=n, material_name="BottleMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name=n, smooth=True))

    tools.append(tool("material_create", name="CapMat",
                       base_color=[0.6, 0.6, 0.62], metallic=r(rand(0.5, 0.9)),
                       roughness=r(rand(0.3, 0.5))))
    tools.append(tool("material_assign", object_name="BottleCap", material_name="CapMat"))

    prompt = (f"Create a {mat_name} bottle, {r(z + cap_h)}m tall with a tapered neck.")
    return prompt, tools, ["bottle", "prop", "tableware", "interior"]


def generate_pot() -> Tuple[str, List, List]:
    """Flower pot - truncated cone, hollow via solidify, optional saucer."""
    top_r = rand(0.06, 0.15)
    bottom_r = rand(top_r * 0.6, top_r * 0.8)
    height = rand(0.08, 0.2)
    wall_thick = rand(0.003, 0.008)
    has_saucer = random.random() < 0.5
    mat_name, mat_color = color_named()
    # Bias to terracotta
    if random.random() < 0.5:
        mat_name = pick("brick red", "orange", "brown")
        mat_color = {"brick red": [0.6, 0.2, 0.1], "orange": [0.75, 0.35, 0.1],
                     "brown": [0.4, 0.2, 0.05]}[mat_name]

    tools = []

    tools.append(tool("mesh_create_primitive", type="CONE", name="FlowerPot",
                       radius1=r(bottom_r), radius2=r(top_r), depth=r(height),
                       vertices=24, location=[0, 0, r(height/2)]))

    tools.append(tool("modifier_add", object_name="FlowerPot", type="SOLIDIFY",
                       properties={"thickness": r(wall_thick), "offset": -1}))

    # Rim (torus at top)
    tools.append(tool("mesh_create_primitive", type="TORUS", name="PotRim",
                       major_radius=r(top_r), minor_radius=r(wall_thick * 1.5),
                       location=[0, 0, r(height)]))

    if has_saucer:
        saucer_r = top_r * rand(1.1, 1.3)
        saucer_h = rand(0.01, 0.02)
        tools.append(tool("mesh_create_primitive", type="CYLINDER", name="PotSaucer",
                           radius=r(saucer_r), depth=r(saucer_h), vertices=24,
                           location=[0, 0, r(-saucer_h/2)]))

    # Material
    tools.append(tool("material_create", name="PotMat",
                       base_color=mat_color, roughness=r(rand(0.6, 0.95))))
    parts = ["FlowerPot", "PotRim"]
    if has_saucer:
        parts.append("PotSaucer")
    for n in parts:
        tools.append(tool("material_assign", object_name=n, material_name="PotMat"))

    tools.append(tool("mesh_set_smooth_shading", object_name="FlowerPot", smooth=True))

    saucer_desc = " with a saucer" if has_saucer else ""
    prompt = (f"Create a {mat_name} flower pot{saucer_desc}, {r(height*100)}cm tall, "
              f"{r(top_r*200)}cm diameter at the top.")
    return prompt, tools, ["pot", "planter", "garden", "prop"]


def generate_snowman() -> Tuple[str, List, List]:
    """Snowman - 3 stacked spheres + nose cone + optional hat."""
    base_r = rand(0.3, 0.5)
    mid_r = rand(base_r * 0.65, base_r * 0.8)
    head_r = rand(mid_r * 0.6, mid_r * 0.75)
    has_hat = random.random() < 0.6

    tools = []

    # Base sphere
    tools.append(tool("mesh_create_primitive", type="SPHERE", name="SnowBase",
                       radius=r(base_r), segments=20, ring_count=14,
                       location=[0, 0, r(base_r)]))

    # Mid sphere
    mid_z = base_r * 2 - mid_r * 0.3
    tools.append(tool("mesh_create_primitive", type="SPHERE", name="SnowMid",
                       radius=r(mid_r), segments=18, ring_count=12,
                       location=[0, 0, r(mid_z + mid_r)]))

    # Head sphere
    head_z = mid_z + mid_r * 2 - head_r * 0.3
    tools.append(tool("mesh_create_primitive", type="SPHERE", name="SnowHead",
                       radius=r(head_r), segments=16, ring_count=10,
                       location=[0, 0, r(head_z + head_r)]))

    # Nose (carrot cone)
    nose_len = rand(0.05, 0.1)
    tools.append(tool("mesh_create_primitive", type="CONE", name="Nose",
                       radius1=r(0.015), radius2=0, depth=r(nose_len),
                       vertices=8,
                       rotation=[0, r(math.radians(90)), 0],
                       location=[0, r(-head_r * 0.9), r(head_z + head_r)]))

    # Eyes (small spheres)
    eye_r = head_r * 0.1
    eye_y = -head_r * 0.8
    for i, x in enumerate([-head_r * 0.3, head_r * 0.3]):
        tools.append(tool("mesh_create_primitive", type="SPHERE",
                          name=f"Eye{i+1}", radius=r(eye_r), segments=8, ring_count=6,
                          location=[r(x), r(eye_y), r(head_z + head_r * 1.2)]))

    if has_hat:
        hat_r = head_r * rand(0.8, 1.0)
        brim_r = hat_r * rand(1.3, 1.6)
        hat_h = rand(0.1, 0.2)
        hat_z = head_z + head_r * 2 - head_r * 0.15
        # Brim
        tools.append(tool("mesh_create_primitive", type="CYLINDER", name="HatBrim",
                           radius=r(brim_r), depth=r(0.015), vertices=24,
                           location=[0, 0, r(hat_z)]))
        # Top
        tools.append(tool("mesh_create_primitive", type="CYLINDER", name="HatTop",
                           radius=r(hat_r), depth=r(hat_h), vertices=24,
                           location=[0, 0, r(hat_z + hat_h/2)]))

    # Materials
    tools.append(tool("material_create", name="SnowMat",
                       base_color=[0.95, 0.95, 0.97], roughness=0.8))
    for n in ["SnowBase", "SnowMid", "SnowHead"]:
        tools.append(tool("material_assign", object_name=n, material_name="SnowMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name=n, smooth=True))

    tools.append(tool("material_create", name="CarrotMat",
                       base_color=[0.9, 0.4, 0.05], roughness=0.7))
    tools.append(tool("material_assign", object_name="Nose", material_name="CarrotMat"))

    tools.append(tool("material_create", name="CoalMat",
                       base_color=[0.05, 0.05, 0.05], roughness=0.9))
    for n in ["Eye1", "Eye2"]:
        tools.append(tool("material_assign", object_name=n, material_name="CoalMat"))

    if has_hat:
        tools.append(tool("material_create", name="HatMat",
                           base_color=[0.05, 0.05, 0.05], roughness=0.7))
        tools.append(tool("material_assign", object_name="HatBrim", material_name="HatMat"))
        tools.append(tool("material_assign", object_name="HatTop", material_name="HatMat"))

    hat_desc = " wearing a top hat" if has_hat else ""
    total_h = head_z + head_r * 2 + (hat_h + 0.015 if has_hat else 0)
    prompt = f"Create a snowman{hat_desc}, about {r(total_h)}m tall, with a carrot nose."
    return prompt, tools, ["snowman", "character", "stylized", "winter"]


def generate_door() -> Tuple[str, List, List]:
    """Door with frame."""
    door_w = rand(0.8, 1.1)
    door_h = rand(1.9, 2.3)
    door_thick = rand(0.03, 0.05)
    frame_w = rand(0.04, 0.08)
    frame_depth = rand(0.06, 0.12)
    mat_name_door, color_door = color_named()
    mat_name_frame, color_frame = color_named()

    tools = []

    # Door panel
    tools.append(tool("mesh_create_primitive", type="CUBE", name="DoorPanel",
                       size=1, scale=[r(door_w/2), r(door_thick/2), r(door_h/2)],
                       location=[0, 0, r(door_h/2)]))

    # Frame pieces
    tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameLeft",
                       size=1, scale=[r(frame_w/2), r(frame_depth/2), r(door_h/2 + frame_w/2)],
                       location=[r(-door_w/2 - frame_w/2), 0, r(door_h/2)]))
    tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameRight",
                       size=1, scale=[r(frame_w/2), r(frame_depth/2), r(door_h/2 + frame_w/2)],
                       location=[r(door_w/2 + frame_w/2), 0, r(door_h/2)]))
    tools.append(tool("mesh_create_primitive", type="CUBE", name="FrameTop",
                       size=1, scale=[r(door_w/2 + frame_w), r(frame_depth/2), r(frame_w/2)],
                       location=[0, 0, r(door_h + frame_w/2)]))

    # Door knob (small sphere)
    knob_side = pick(-1, 1)
    tools.append(tool("mesh_create_primitive", type="SPHERE", name="DoorKnob",
                       radius=r(0.015), segments=10, ring_count=8,
                       location=[r(knob_side * door_w * 0.4), r(-door_thick/2 - 0.01),
                                 r(door_h * 0.5)]))

    # Materials
    tools.append(tool("material_create", name="DoorMat",
                       base_color=color_door, roughness=r(rand(0.4, 0.8))))
    tools.append(tool("material_assign", object_name="DoorPanel", material_name="DoorMat"))

    tools.append(tool("material_create", name="DoorFrameMat",
                       base_color=color_frame, roughness=r(rand(0.5, 0.8))))
    for n in ["FrameLeft", "FrameRight", "FrameTop"]:
        tools.append(tool("material_assign", object_name=n, material_name="DoorFrameMat"))

    tools.append(tool("material_create", name="KnobMat",
                       base_color=[0.7, 0.65, 0.3], metallic=0.8, roughness=0.3))
    tools.append(tool("material_assign", object_name="DoorKnob", material_name="KnobMat"))
    tools.append(tool("mesh_set_smooth_shading", object_name="DoorKnob", smooth=True))

    prompt = (f"Create a {mat_name_door} door with a {mat_name_frame} frame and "
              f"brass knob, {r(door_w)}m wide and {r(door_h)}m tall.")
    return prompt, tools, ["door", "architecture", "building", "interior"]


def generate_candle() -> Tuple[str, List, List]:
    """Simple candle - cylinder + small flame cone."""
    radius = rand(0.01, 0.04)
    height = rand(0.06, 0.2)
    has_flame = random.random() < 0.7
    mat_name, mat_color = color_named()
    if random.random() < 0.6:
        mat_name = pick("white", "cream", "red")
        mat_color = {"white": [0.95, 0.93, 0.9], "cream": [0.95, 0.9, 0.8],
                     "red": [0.7, 0.1, 0.1]}[mat_name]

    tools = []

    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="CandleBody",
                       radius=r(radius), depth=r(height), vertices=16,
                       location=[0, 0, r(height/2)]))

    if has_flame:
        flame_h = rand(0.015, 0.03)
        tools.append(tool("mesh_create_primitive", type="CONE", name="Flame",
                           radius1=r(radius * 0.3), radius2=0, depth=r(flame_h),
                           vertices=8, location=[0, 0, r(height + flame_h/2)]))
        tools.append(tool("material_create", name="FlameMat",
                           base_color=[1.0, 0.7, 0.1],
                           emission=[1.0, 0.6, 0.1], emission_strength=r(rand(3, 8))))
        tools.append(tool("material_assign", object_name="Flame", material_name="FlameMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name="Flame", smooth=True))

    tools.append(tool("material_create", name="WaxMat",
                       base_color=mat_color, roughness=r(rand(0.7, 0.95))))
    tools.append(tool("material_assign", object_name="CandleBody", material_name="WaxMat"))
    tools.append(tool("mesh_set_smooth_shading", object_name="CandleBody", smooth=True))

    flame_desc = " with a lit flame" if has_flame else ""
    prompt = f"Create a {mat_name} candle{flame_desc}, {r(height*100)}cm tall."
    return prompt, tools, ["candle", "prop", "interior", "medieval"]


def generate_goblet() -> Tuple[str, List, List]:
    """Goblet/chalice - base disc, thin stem, bowl (sphere top half effect via cone+sphere)."""
    base_r = rand(0.025, 0.04)
    base_h = rand(0.005, 0.01)
    stem_r = rand(0.004, 0.008)
    stem_h = rand(0.04, 0.08)
    bowl_r = rand(0.025, 0.045)
    mat_name, mat_color = color_named()
    if random.random() < 0.5:
        mat_name = pick("gold", "steel", "copper", "brass")
        mat_color = {"gold": [0.83, 0.69, 0.22], "steel": [0.6, 0.6, 0.65],
                     "copper": [0.72, 0.45, 0.2], "brass": [0.71, 0.65, 0.26]}[mat_name]

    tools = []
    z = 0

    # Base
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="GobletBase",
                       radius=r(base_r), depth=r(base_h), vertices=24,
                       location=[0, 0, r(base_h/2)]))
    z += base_h

    # Stem
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="GobletStem",
                       radius=r(stem_r), depth=r(stem_h), vertices=12,
                       location=[0, 0, r(z + stem_h/2)]))
    z += stem_h

    # Bowl (cone flaring out + sphere top)
    flare_h = rand(0.015, 0.025)
    tools.append(tool("mesh_create_primitive", type="CONE", name="GobletFlare",
                       radius1=r(stem_r), radius2=r(bowl_r), depth=r(flare_h),
                       vertices=24, location=[0, 0, r(z + flare_h/2)]))
    z += flare_h

    bowl_h = rand(0.03, 0.05)
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="GobletBowl",
                       radius=r(bowl_r), depth=r(bowl_h), vertices=24,
                       location=[0, 0, r(z + bowl_h/2)]))
    tools.append(tool("modifier_add", object_name="GobletBowl", type="SOLIDIFY",
                       properties={"thickness": r(0.002), "offset": -1}))

    # Material
    tools.append(tool("material_create", name="GobletMat",
                       base_color=mat_color, metallic=r(rand(0.6, 0.95)),
                       roughness=r(rand(0.15, 0.4))))
    for n in ["GobletBase", "GobletStem", "GobletFlare", "GobletBowl"]:
        tools.append(tool("material_assign", object_name=n, material_name="GobletMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name=n, smooth=True))

    prompt = f"Create a {mat_name} goblet, {r((z + bowl_h)*100)}cm tall."
    return prompt, tools, ["goblet", "chalice", "tableware", "medieval", "prop"]


def generate_street_lamp() -> Tuple[str, List, List]:
    """Street lamp - tall pole with a lamp head on top."""
    pole_r = rand(0.03, 0.06)
    pole_h = rand(2.5, 4.5)
    base_r = rand(0.1, 0.2)
    base_h = rand(0.05, 0.15)
    lamp_r = rand(0.08, 0.15)
    lamp_h = rand(0.15, 0.3)
    mat_name, mat_color = color_named()
    if random.random() < 0.6:
        mat_name = pick("black", "dark green", "metal gray")
        mat_color = {"black": [0.05, 0.05, 0.05], "dark green": [0.05, 0.2, 0.08],
                     "metal gray": [0.35, 0.35, 0.37]}[mat_name]

    tools = []
    z = 0

    # Base
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="LampPostBase",
                       radius=r(base_r), depth=r(base_h), vertices=8,
                       location=[0, 0, r(base_h/2)]))
    z += base_h

    # Pole
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="LampPostPole",
                       radius=r(pole_r), depth=r(pole_h), vertices=8,
                       location=[0, 0, r(z + pole_h/2)]))
    z += pole_h

    # Lamp housing (inverted cone + sphere)
    tools.append(tool("mesh_create_primitive", type="CONE", name="LampHousing",
                       radius1=r(lamp_r), radius2=r(pole_r * 1.5), depth=r(lamp_h),
                       vertices=16, location=[0, 0, r(z + lamp_h/2)]))

    # Light bulb (glowing sphere inside)
    tools.append(tool("mesh_create_primitive", type="SPHERE", name="LampBulb",
                       radius=r(lamp_r * 0.5), segments=12, ring_count=8,
                       location=[0, 0, r(z + lamp_h * 0.3)]))

    # Materials
    tools.append(tool("material_create", name="PostMat",
                       base_color=mat_color, metallic=r(rand(0.4, 0.8)),
                       roughness=r(rand(0.4, 0.7))))
    for n in ["LampPostBase", "LampPostPole", "LampHousing"]:
        tools.append(tool("material_assign", object_name=n, material_name="PostMat"))

    tools.append(tool("material_create", name="BulbMat",
                       base_color=[1.0, 0.95, 0.8],
                       emission=[1.0, 0.9, 0.7], emission_strength=r(rand(5, 15))))
    tools.append(tool("material_assign", object_name="LampBulb", material_name="BulbMat"))
    tools.append(tool("mesh_set_smooth_shading", object_name="LampBulb", smooth=True))
    tools.append(tool("mesh_set_smooth_shading", object_name="LampHousing", smooth=True))

    prompt = (f"Create a {mat_name} street lamp, {r(z + lamp_h)}m tall with a "
              f"glowing bulb.")
    return prompt, tools, ["street_lamp", "exterior", "urban", "prop"]


def generate_tombstone() -> Tuple[str, List, List]:
    """Tombstone - slab with rounded/flat top."""
    w = rand(0.4, 0.8)
    h = rand(0.6, 1.2)
    d = rand(0.08, 0.15)
    style = pick("flat", "rounded")
    mat_name, mat_color = color_named()
    if random.random() < 0.7:
        mat_name = pick("stone gray", "gray", "light gray")
        mat_color = {"stone gray": [0.55, 0.55, 0.5], "gray": [0.4, 0.4, 0.4],
                     "light gray": [0.7, 0.7, 0.7]}[mat_name]

    tools = []

    if style == "flat":
        tools.append(tool("mesh_create_primitive", type="CUBE", name="Tombstone",
                           size=1, scale=[r(w/2), r(d/2), r(h/2)],
                           location=[0, 0, r(h/2)]))
        # Bevel the top edges
        tools.append(tool("modifier_add", object_name="Tombstone", type="BEVEL",
                           properties={"width": r(rand(0.01, 0.03)), "segments": 2}))
    else:
        # Rectangular body + half-cylinder top
        body_h = h * 0.7
        tools.append(tool("mesh_create_primitive", type="CUBE", name="Tombstone",
                           size=1, scale=[r(w/2), r(d/2), r(body_h/2)],
                           location=[0, 0, r(body_h/2)]))
        tools.append(tool("mesh_create_primitive", type="CYLINDER", name="TombstoneTop",
                           radius=r(w/2), depth=r(d), vertices=24,
                           rotation=[r(math.radians(90)), 0, 0],
                           scale=[1, 1, 1],
                           location=[0, 0, r(body_h)]))

    tools.append(tool("material_create", name="StoneMat",
                       base_color=mat_color, roughness=r(rand(0.7, 0.98))))
    tools.append(tool("material_assign", object_name="Tombstone", material_name="StoneMat"))
    if style == "rounded":
        tools.append(tool("material_assign", object_name="TombstoneTop",
                           material_name="StoneMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name="TombstoneTop", smooth=True))

    prompt = (f"Create a {style}-top {mat_name} tombstone, {r(w)}m wide and {r(h)}m tall.")
    return prompt, tools, ["tombstone", "graveyard", "prop", "medieval"]


def generate_signpost() -> Tuple[str, List, List]:
    """Signpost - pole + flat board sign."""
    pole_r = rand(0.02, 0.04)
    pole_h = rand(1.5, 2.5)
    sign_w = rand(0.4, 0.8)
    sign_h = rand(0.2, 0.4)
    sign_thick = rand(0.015, 0.03)
    mat_pole, color_pole = color_named()
    mat_sign, color_sign = color_named()
    if random.random() < 0.6:
        mat_pole = pick("wood brown", "brown", "dark brown")
        color_pole = {"wood brown": [0.45, 0.28, 0.1], "brown": [0.4, 0.2, 0.05],
                      "dark brown": [0.25, 0.12, 0.03]}[mat_pole]

    tools = []

    # Pole
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="SignPole",
                       radius=r(pole_r), depth=r(pole_h), vertices=8,
                       location=[0, 0, r(pole_h/2)]))

    # Sign board
    sign_z = pole_h * rand(0.7, 0.9)
    tools.append(tool("mesh_create_primitive", type="CUBE", name="SignBoard",
                       size=1, scale=[r(sign_w/2), r(sign_thick/2), r(sign_h/2)],
                       location=[r(sign_w/2 + pole_r), 0, r(sign_z)]))

    # Materials
    tools.append(tool("material_create", name="PoleMat",
                       base_color=color_pole, roughness=r(rand(0.6, 0.9))))
    tools.append(tool("material_assign", object_name="SignPole", material_name="PoleMat"))

    tools.append(tool("material_create", name="SignMat",
                       base_color=color_sign, roughness=r(rand(0.5, 0.8))))
    tools.append(tool("material_assign", object_name="SignBoard", material_name="SignMat"))

    prompt = (f"Create a {mat_pole} signpost {r(pole_h)}m tall with a "
              f"{mat_sign} sign board.")
    return prompt, tools, ["signpost", "sign", "exterior", "prop"]


def generate_rock() -> Tuple[str, List, List]:
    """Stylized rock - ico sphere with displacement-like random scaling."""
    radius = rand(0.2, 1.0)
    subdivisions = pick(2, 3)
    squish_z = rand(0.4, 0.8)
    stretch_x = rand(0.8, 1.4)
    mat_name, mat_color = color_named()
    if random.random() < 0.7:
        mat_name = pick("stone gray", "gray", "dark gray", "brown")
        mat_color = {"stone gray": [0.55, 0.55, 0.5], "gray": [0.45, 0.45, 0.45],
                     "dark gray": [0.3, 0.3, 0.3], "brown": [0.35, 0.22, 0.1]}[mat_name]

    tools = []

    tools.append(tool("mesh_create_primitive", type="SPHERE", name="Rock",
                       radius=r(radius), segments=subdivisions,
                       scale=[r(stretch_x), 1, r(squish_z)],
                       location=[0, 0, r(radius * squish_z)]))

    # Subdivide for more organic look
    tools.append(tool("modifier_add", object_name="Rock", type="SUBSURF",
                       properties={"levels": 1, "render_levels": 2}))

    tools.append(tool("material_create", name="RockMat",
                       base_color=mat_color, roughness=r(rand(0.8, 1.0))))
    tools.append(tool("material_assign", object_name="Rock", material_name="RockMat"))
    tools.append(tool("mesh_set_smooth_shading", object_name="Rock", smooth=True))

    prompt = (f"Create a {mat_name} rock, roughly {r(radius*2*stretch_x)}m wide "
              f"and {r(radius*2*squish_z)}m tall.")
    return prompt, tools, ["rock", "stone", "nature", "environment"]


def generate_chest() -> Tuple[str, List, List]:
    """Treasure chest - box body + curved lid + bands."""
    w = rand(0.3, 0.8)
    d = rand(0.2, 0.5)
    body_h = rand(0.15, 0.35)
    lid_r = d / 2
    mat_body, color_body = color_named()
    mat_band, color_band = color_named()
    if random.random() < 0.6:
        mat_body = pick("wood brown", "oak", "pine", "dark brown")
        color_body = {"wood brown": [0.45, 0.28, 0.1], "oak": [0.5, 0.35, 0.15],
                      "pine": [0.6, 0.45, 0.2], "dark brown": [0.25, 0.12, 0.03]}[mat_body]
    if random.random() < 0.6:
        mat_band = pick("gold", "brass", "steel", "copper")
        color_band = {"gold": [0.83, 0.69, 0.22], "brass": [0.71, 0.65, 0.26],
                      "steel": [0.6, 0.6, 0.65], "copper": [0.72, 0.45, 0.2]}[mat_band]

    tools = []

    # Body
    tools.append(tool("mesh_create_primitive", type="CUBE", name="ChestBody",
                       size=1, scale=[r(w/2), r(d/2), r(body_h/2)],
                       location=[0, 0, r(body_h/2)]))

    # Lid (half cylinder)
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="ChestLid",
                       radius=r(lid_r), depth=r(w), vertices=24,
                       rotation=[0, r(math.radians(90)), 0],
                       location=[0, 0, r(body_h)]))

    # Metal bands
    band_thick = rand(0.008, 0.015)
    for i, x_pct in enumerate([-0.35, 0, 0.35]):
        x = w * x_pct
        tools.append(tool("mesh_create_primitive", type="CUBE",
                          name=f"Band{i+1}", size=1,
                          scale=[r(band_thick/2), r(d/2 * 1.05), r(body_h/2 * 1.02)],
                          location=[r(x), 0, r(body_h/2)]))

    # Lock (small cube on front)
    tools.append(tool("mesh_create_primitive", type="CUBE", name="Lock",
                       size=r(0.03),
                       location=[0, r(-d/2 - 0.01), r(body_h * 0.7)]))

    # Materials
    tools.append(tool("material_create", name="ChestWood",
                       base_color=color_body, roughness=r(rand(0.6, 0.9))))
    tools.append(tool("material_assign", object_name="ChestBody", material_name="ChestWood"))
    tools.append(tool("material_assign", object_name="ChestLid", material_name="ChestWood"))

    tools.append(tool("material_create", name="ChestMetal",
                       base_color=color_band, metallic=r(rand(0.6, 0.9)),
                       roughness=r(rand(0.3, 0.5))))
    for n in ["Band0", "Band1", "Band2", "Lock"]:
        nm = n if n == "Lock" else f"Band{int(n[-1])+1}" if n.startswith("Band") else n
    for i in range(3):
        tools.append(tool("material_assign", object_name=f"Band{i+1}",
                           material_name="ChestMetal"))
    tools.append(tool("material_assign", object_name="Lock", material_name="ChestMetal"))

    tools.append(tool("mesh_set_smooth_shading", object_name="ChestLid", smooth=True))

    prompt = (f"Create a {mat_body} treasure chest with {mat_band} metal bands, "
              f"{r(w)}m wide.")
    return prompt, tools, ["chest", "treasure", "medieval", "prop", "container"]


def generate_ladder() -> Tuple[str, List, List]:
    """Ladder - two side rails + rungs."""
    height = rand(1.5, 3.5)
    width = rand(0.35, 0.55)
    n_rungs = random.randint(4, 10)
    rail_thick = rand(0.02, 0.04)
    rung_r = rand(0.01, 0.02)
    mat_name, mat_color = color_named()
    if random.random() < 0.6:
        mat_name = pick("wood brown", "pine", "oak")
        mat_color = {"wood brown": [0.45, 0.28, 0.1], "pine": [0.6, 0.45, 0.2],
                     "oak": [0.5, 0.35, 0.15]}[mat_name]

    # Lean angle
    lean = rand(0.1, 0.25)  # slight tilt in Y

    tools = []

    # Left rail
    tools.append(tool("mesh_create_primitive", type="CUBE", name="RailLeft",
                       size=1, scale=[r(rail_thick/2), r(rail_thick/2), r(height/2)],
                       location=[r(-width/2), 0, r(height/2)]))
    # Right rail
    tools.append(tool("mesh_create_primitive", type="CUBE", name="RailRight",
                       size=1, scale=[r(rail_thick/2), r(rail_thick/2), r(height/2)],
                       location=[r(width/2), 0, r(height/2)]))

    # Rungs
    spacing = height / (n_rungs + 1)
    for i in range(n_rungs):
        z = spacing * (i + 1)
        tools.append(tool("mesh_create_primitive", type="CYLINDER",
                          name=f"Rung{i+1}", radius=r(rung_r), depth=r(width),
                          vertices=8,
                          rotation=[0, r(math.radians(90)), 0],
                          location=[0, 0, r(z)]))

    # Material
    tools.append(tool("material_create", name="LadderMat",
                       base_color=mat_color, roughness=r(rand(0.6, 0.9))))
    parts = ["RailLeft", "RailRight"] + [f"Rung{i+1}" for i in range(n_rungs)]
    for n in parts:
        tools.append(tool("material_assign", object_name=n, material_name="LadderMat"))

    prompt = (f"Create a {mat_name} ladder, {r(height)}m tall with {n_rungs} rungs.")
    return prompt, tools, ["ladder", "prop", "tool", "construction"]


def generate_table_round() -> Tuple[str, List, List]:
    """Round table with single pedestal base."""
    top_r = rand(0.35, 0.7)
    top_h = rand(0.03, 0.06)
    pedestal_r = rand(0.06, 0.12)
    pedestal_h = rand(0.5, 0.9)
    foot_r = rand(top_r * 0.6, top_r * 0.9)
    foot_h = rand(0.02, 0.05)
    mat_name, mat_color = color_named()

    tools = []

    # Foot (wide disc)
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="PedestalFoot",
                       radius=r(foot_r), depth=r(foot_h), vertices=32,
                       location=[0, 0, r(foot_h/2)]))

    # Pedestal column
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="Pedestal",
                       radius=r(pedestal_r), depth=r(pedestal_h), vertices=16,
                       location=[0, 0, r(foot_h + pedestal_h/2)]))

    # Round top
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="RoundTop",
                       radius=r(top_r), depth=r(top_h), vertices=32,
                       location=[0, 0, r(foot_h + pedestal_h + top_h/2)]))

    # Bevel on top edge
    tools.append(tool("modifier_add", object_name="RoundTop", type="BEVEL",
                       properties={"width": r(rand(0.005, 0.015)), "segments": 3}))

    # Material
    tools.append(tool("material_create", name="RoundTableMat",
                       base_color=mat_color, roughness=r(rand(0.3, 0.7))))
    for n in ["PedestalFoot", "Pedestal", "RoundTop"]:
        tools.append(tool("material_assign", object_name=n, material_name="RoundTableMat"))
        tools.append(tool("mesh_set_smooth_shading", object_name=n, smooth=True))

    total_h = foot_h + pedestal_h + top_h
    prompt = (f"Create a {mat_name} round pedestal table, {r(top_r*2)}m diameter, "
              f"{r(total_h)}m tall.")
    return prompt, tools, ["table", "round_table", "furniture", "interior"]


def generate_campfire() -> Tuple[str, List, List]:
    """Campfire - ring of rocks + logs + fire cone."""
    ring_r = rand(0.3, 0.5)
    n_rocks = random.randint(6, 10)
    rock_r = rand(0.05, 0.1)
    n_logs = random.randint(3, 5)
    log_r = rand(0.03, 0.06)
    log_len = rand(0.3, 0.5)

    tools = []

    # Rock ring
    for i in range(n_rocks):
        angle = (2 * math.pi * i) / n_rocks
        x = ring_r * math.cos(angle)
        y = ring_r * math.sin(angle)
        squish = rand(0.5, 0.9)
        tools.append(tool("mesh_create_primitive", type="SPHERE",
                          name=f"Rock{i+1}", radius=r(rock_r), segments=2,
                          scale=[r(rand(0.8, 1.2)), r(rand(0.8, 1.2)), r(squish)],
                          location=[r(x), r(y), r(rock_r * squish)]))

    # Logs (cylinders at angles)
    for i in range(n_logs):
        angle = (2 * math.pi * i) / n_logs + rand(-0.3, 0.3)
        tip_x = ring_r * 0.3 * math.cos(angle)
        tip_y = ring_r * 0.3 * math.sin(angle)
        base_x = ring_r * 0.9 * math.cos(angle)
        base_y = ring_r * 0.9 * math.sin(angle)
        mid_x = (tip_x + base_x) / 2
        mid_y = (tip_y + base_y) / 2
        rot_z = math.atan2(tip_y - base_y, tip_x - base_x)
        tools.append(tool("mesh_create_primitive", type="CYLINDER",
                          name=f"Log{i+1}", radius=r(log_r), depth=r(log_len),
                          vertices=8,
                          rotation=[r(math.radians(90)), 0, r(rot_z)],
                          location=[r(mid_x), r(mid_y), r(log_r + 0.02)]))

    # Fire (cone with emission)
    fire_h = rand(0.2, 0.5)
    tools.append(tool("mesh_create_primitive", type="CONE", name="Fire",
                       radius1=r(ring_r * 0.4), radius2=0, depth=r(fire_h),
                       vertices=8, location=[0, 0, r(fire_h/2 + 0.05)]))

    # Materials
    tools.append(tool("material_create", name="CampRockMat",
                       base_color=[0.4, 0.38, 0.35], roughness=0.95))
    for i in range(n_rocks):
        tools.append(tool("material_assign", object_name=f"Rock{i+1}",
                           material_name="CampRockMat"))

    tools.append(tool("material_create", name="LogMat",
                       base_color=[0.3, 0.18, 0.07], roughness=0.85))
    for i in range(n_logs):
        tools.append(tool("material_assign", object_name=f"Log{i+1}",
                           material_name="LogMat"))

    tools.append(tool("material_create", name="FireMat",
                       base_color=[1.0, 0.4, 0.0],
                       emission=[1.0, 0.35, 0.0], emission_strength=r(rand(8, 20))))
    tools.append(tool("material_assign", object_name="Fire", material_name="FireMat"))
    tools.append(tool("mesh_set_smooth_shading", object_name="Fire", smooth=True))

    prompt = (f"Create a campfire with {n_rocks} stones, {n_logs} logs, and flames.")
    return prompt, tools, ["campfire", "fire", "outdoor", "prop", "medieval"]


def generate_bookstack() -> Tuple[str, List, List]:
    """Stack of books - random colored rectangles stacked with slight offsets."""
    n_books = random.randint(3, 7)
    base_w = rand(0.12, 0.2)
    base_d = rand(0.08, 0.15)

    tools = []
    z = 0

    for i in range(n_books):
        book_h = rand(0.015, 0.035)
        w = base_w * rand(0.85, 1.1)
        d = base_d * rand(0.85, 1.1)
        offset_x = rand(-0.01, 0.01)
        offset_y = rand(-0.01, 0.01)
        rot_z = rand(-0.05, 0.05)

        tools.append(tool("mesh_create_primitive", type="CUBE",
                          name=f"Book{i+1}", size=1,
                          scale=[r(w/2), r(d/2), r(book_h/2)],
                          rotation=[0, 0, r(rot_z)],
                          location=[r(offset_x), r(offset_y), r(z + book_h/2)]))

        bname, bcolor = color_named()
        mat_id = f"BookMat{i+1}"
        tools.append(tool("material_create", name=mat_id,
                           base_color=bcolor, roughness=r(rand(0.5, 0.9))))
        tools.append(tool("material_assign", object_name=f"Book{i+1}",
                           material_name=mat_id))

        z += book_h

    prompt = f"Create a stack of {n_books} colorful books, {r(z*100)}cm tall."
    return prompt, tools, ["books", "bookstack", "prop", "interior"]


def generate_anvil_simple() -> Tuple[str, List, List]:
    """Simple anvil shape - cube base + cube body + cylinder horn."""
    base_w = rand(0.2, 0.35)
    base_d = rand(0.12, 0.2)
    base_h = rand(0.05, 0.1)
    body_w = rand(base_w * 0.6, base_w * 0.85)
    body_h = rand(0.08, 0.15)
    horn_r = rand(0.02, 0.04)
    horn_len = rand(0.08, 0.15)

    tools = []
    z = 0

    # Base (wider)
    tools.append(tool("mesh_create_primitive", type="CUBE", name="AnvilBase",
                       size=1, scale=[r(base_w/2), r(base_d/2), r(base_h/2)],
                       location=[0, 0, r(base_h/2)]))
    z += base_h

    # Body
    tools.append(tool("mesh_create_primitive", type="CUBE", name="AnvilBody",
                       size=1, scale=[r(body_w/2), r(base_d/2 * 0.9), r(body_h/2)],
                       location=[0, 0, r(z + body_h/2)]))

    # Top face (wider flat surface)
    top_h = rand(0.02, 0.04)
    tools.append(tool("mesh_create_primitive", type="CUBE", name="AnvilTop",
                       size=1, scale=[r(base_w/2 * 1.05), r(base_d/2), r(top_h/2)],
                       location=[0, 0, r(z + body_h + top_h/2)]))

    # Horn (cone sticking out one end)
    tools.append(tool("mesh_create_primitive", type="CONE", name="AnvilHorn",
                       radius1=r(horn_r), radius2=r(horn_r * 0.3), depth=r(horn_len),
                       vertices=12,
                       rotation=[0, r(math.radians(-90)), 0],
                       location=[r(base_w/2 + horn_len/2), 0, r(z + body_h + top_h/2)]))

    # Material
    tools.append(tool("material_create", name="AnvilMat",
                       base_color=[0.25, 0.25, 0.27], metallic=0.85, roughness=0.45))
    for n in ["AnvilBase", "AnvilBody", "AnvilTop", "AnvilHorn"]:
        tools.append(tool("material_assign", object_name=n, material_name="AnvilMat"))
    tools.append(tool("mesh_set_smooth_shading", object_name="AnvilHorn", smooth=True))

    total_h = z + body_h + top_h
    prompt = f"Create an iron anvil, {r(base_w)}m wide and {r(total_h)}m tall with a horn."
    return prompt, tools, ["anvil", "blacksmith", "medieval", "prop", "tool"]


def generate_wheel() -> Tuple[str, List, List]:
    """Simple wheel - torus rim + cylinder hub + cube spokes."""
    rim_r = rand(0.2, 0.5)
    rim_thick = rand(0.015, 0.035)
    hub_r = rand(rim_r * 0.15, rim_r * 0.25)
    hub_d = rand(0.03, 0.06)
    n_spokes = pick(4, 6, 8)
    spoke_thick = rand(0.008, 0.015)
    mat_name, mat_color = color_named()
    if random.random() < 0.6:
        mat_name = pick("wood brown", "oak", "dark brown")
        mat_color = {"wood brown": [0.45, 0.28, 0.1], "oak": [0.5, 0.35, 0.15],
                     "dark brown": [0.25, 0.12, 0.03]}[mat_name]

    tools = []

    # Rim (torus)
    tools.append(tool("mesh_create_primitive", type="TORUS", name="WheelRim",
                       major_radius=r(rim_r), minor_radius=r(rim_thick),
                       major_segments=32, minor_segments=12,
                       rotation=[r(math.radians(90)), 0, 0],
                       location=[0, 0, r(rim_r + rim_thick)]))

    # Hub
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="WheelHub",
                       radius=r(hub_r), depth=r(hub_d), vertices=16,
                       rotation=[r(math.radians(90)), 0, 0],
                       location=[0, 0, r(rim_r + rim_thick)]))

    # Spokes
    spoke_len = rim_r - hub_r
    for i in range(n_spokes):
        angle = (2 * math.pi * i) / n_spokes
        cx = (hub_r + rim_r) / 2 * math.cos(angle)
        cz = (hub_r + rim_r) / 2 * math.sin(angle) + rim_r + rim_thick
        tools.append(tool("mesh_create_primitive", type="CUBE",
                          name=f"Spoke{i+1}", size=1,
                          scale=[r(spoke_len/2), r(spoke_thick/2), r(spoke_thick/2)],
                          rotation=[0, 0, r(angle)],
                          location=[r(cx), 0, r(cz)]))

    # Material
    tools.append(tool("material_create", name="WheelMat",
                       base_color=mat_color, roughness=r(rand(0.6, 0.9))))
    parts = ["WheelRim", "WheelHub"] + [f"Spoke{i+1}" for i in range(n_spokes)]
    for n in parts:
        tools.append(tool("material_assign", object_name=n, material_name="WheelMat"))
    tools.append(tool("mesh_set_smooth_shading", object_name="WheelRim", smooth=True))
    tools.append(tool("mesh_set_smooth_shading", object_name="WheelHub", smooth=True))

    prompt = (f"Create a {mat_name} wheel with {n_spokes} spokes, "
              f"{r(rim_r*2)}m diameter.")
    return prompt, tools, ["wheel", "prop", "medieval", "vehicle_part"]


def generate_torch() -> Tuple[str, List, List]:
    """Wall torch - handle + flame."""
    handle_r = rand(0.015, 0.025)
    handle_h = rand(0.25, 0.45)
    head_r = rand(0.025, 0.04)
    head_h = rand(0.04, 0.08)
    mat_name = pick("wood brown", "dark brown")
    mat_color = {"wood brown": [0.45, 0.28, 0.1], "dark brown": [0.25, 0.12, 0.03]}[mat_name]

    tools = []

    # Handle
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="TorchHandle",
                       radius=r(handle_r), depth=r(handle_h), vertices=8,
                       location=[0, 0, r(handle_h/2)]))

    # Wrap/head (slightly wider)
    tools.append(tool("mesh_create_primitive", type="CYLINDER", name="TorchHead",
                       radius=r(head_r), depth=r(head_h), vertices=12,
                       location=[0, 0, r(handle_h + head_h/2)]))

    # Flame
    flame_h = rand(0.06, 0.15)
    tools.append(tool("mesh_create_primitive", type="CONE", name="TorchFlame",
                       radius1=r(head_r * 0.8), radius2=0, depth=r(flame_h),
                       vertices=8,
                       location=[0, 0, r(handle_h + head_h + flame_h/2)]))

    # Materials
    tools.append(tool("material_create", name="TorchWood",
                       base_color=mat_color, roughness=0.85))
    tools.append(tool("material_assign", object_name="TorchHandle", material_name="TorchWood"))

    tools.append(tool("material_create", name="TorchWrap",
                       base_color=[0.3, 0.15, 0.05], roughness=0.9))
    tools.append(tool("material_assign", object_name="TorchHead", material_name="TorchWrap"))

    tools.append(tool("material_create", name="TorchFire",
                       base_color=[1.0, 0.5, 0.0],
                       emission=[1.0, 0.4, 0.0], emission_strength=r(rand(10, 25))))
    tools.append(tool("material_assign", object_name="TorchFlame", material_name="TorchFire"))
    tools.append(tool("mesh_set_smooth_shading", object_name="TorchFlame", smooth=True))

    prompt = f"Create a lit torch, {r(handle_h + head_h + flame_h)}m tall."
    return prompt, tools, ["torch", "medieval", "prop", "light"]


# ---------------------------------------------------------------------------
# Registry of all generators
# ---------------------------------------------------------------------------

GENERATORS = {
    # Simple furniture
    "table": generate_table,
    "table_round": generate_table_round,
    "chair": generate_chair,
    "bench": generate_bench,
    "shelf": generate_shelf,
    "lamp": generate_lamp,
    # Props & containers
    "barrel": generate_barrel,
    "crate": generate_crate,
    "chest": generate_chest,
    "bottle": generate_bottle,
    "cup": generate_cup,
    "pot": generate_pot,
    "goblet": generate_goblet,
    "bookstack": generate_bookstack,
    # Architecture
    "pillar": generate_pillar,
    "wall": generate_wall,
    "arch": generate_arch,
    "staircase": generate_staircase,
    "platform": generate_platform,
    "fence": generate_fence,
    "door": generate_door,
    "window_frame": generate_window_frame,
    "tower": generate_tower,
    "well": generate_well,
    # Nature & outdoor
    "tree": generate_tree_simple,
    "rock": generate_rock,
    "mushroom": generate_mushroom,
    "campfire": generate_campfire,
    # Medieval / fantasy props
    "candlestick": generate_candlestick,
    "candle": generate_candle,
    "torch": generate_torch,
    "tombstone": generate_tombstone,
    "signpost": generate_signpost,
    "anvil": generate_anvil_simple,
    "wheel": generate_wheel,
    "street_lamp": generate_street_lamp,
    "snowman": generate_snowman,
    "ladder": generate_ladder,
}


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_raw(sample: dict) -> dict:
    """Raw JSON format."""
    return sample


def format_chatml(sample: dict) -> dict:
    """ChatML format for fine-tuning."""
    tool_calls_text = []
    for t in sample["tools"]:
        params_str = json.dumps(t["params"], separators=(",", ":"))
        tool_calls_text.append(f'{t["tool"]}({params_str})')

    return {
        "messages": [
            {"role": "system", "content": "You are a 3D modeling assistant that builds objects in Blender using MCP tools. Given a description, output the sequence of tool calls to build the object."},
            {"role": "user", "content": sample["prompt"]},
            {"role": "assistant", "content": "\n".join(tool_calls_text)},
        ]
    }


def format_tool_use(sample: dict) -> dict:
    """Anthropic tool_use format."""
    messages = [
        {"role": "user", "content": sample["prompt"]},
    ]
    tool_calls = []
    for t in sample["tools"]:
        tool_calls.append({
            "type": "tool_use",
            "name": t["tool"],
            "input": t["params"],
        })
    messages.append({
        "role": "assistant",
        "content": tool_calls,
    })
    return {"messages": messages}


FORMATTERS = {
    "raw": format_raw,
    "chatml": format_chatml,
    "tool_use": format_tool_use,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Procedural 3D training data generator")
    parser.add_argument("--count", type=int, default=100,
                        help="Number of samples to generate (default: 100)")
    parser.add_argument("--output", type=str, default="./generated/",
                        help="Output directory")
    parser.add_argument("--category", nargs="*", default=None,
                        help="Specific categories (default: all)")
    parser.add_argument("--format", choices=["raw", "chatml", "tool_use"],
                        default="raw", help="Output format (default: raw)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    parser.add_argument("--split", action="store_true",
                        help="Split into train/val (90/10)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    categories = args.category or list(GENERATORS.keys())
    for c in categories:
        if c not in GENERATORS:
            print(f"ERROR: unknown category '{c}'. Available: {', '.join(GENERATORS.keys())}")
            sys.exit(1)

    formatter = FORMATTERS[args.format]
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} samples across {len(categories)} categories...")
    print(f"Categories: {', '.join(categories)}")
    print(f"Format: {args.format}")

    samples = []
    for i in range(args.count):
        cat = random.choice(categories)
        gen = GENERATORS[cat]
        prompt, tools, tags = gen()

        sample = {
            "id": i,
            "category": cat,
            "tags": tags,
            "prompt": prompt,
            "tools": tools,
            "tool_count": len(tools),
        }
        samples.append(formatter(sample))

    # Stats
    cat_counts = {}
    tool_counts = []
    for s in samples:
        raw = s if "category" in s else s.get("messages", [{}])
        if "category" in s:
            cat_counts[s["category"]] = cat_counts.get(s["category"], 0) + 1
            tool_counts.append(s["tool_count"])

    if args.split:
        split_idx = int(len(samples) * 0.9)
        random.shuffle(samples)
        train = samples[:split_idx]
        val = samples[split_idx:]

        train_path = output_dir / f"train_{args.count}.jsonl"
        val_path = output_dir / f"val_{args.count}.jsonl"

        with open(train_path, "w") as f:
            for s in train:
                f.write(json.dumps(s) + "\n")
        with open(val_path, "w") as f:
            for s in val:
                f.write(json.dumps(s) + "\n")

        print(f"\nWrote {len(train)} train -> {train_path}")
        print(f"Wrote {len(val)} val -> {val_path}")
    else:
        out_path = output_dir / f"training_{args.count}.jsonl"
        with open(out_path, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")
        print(f"\nWrote {len(samples)} samples -> {out_path}")

    # Print stats
    if cat_counts:
        print(f"\nCategory distribution:")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")
        if tool_counts:
            print(f"\nTool calls per sample: min={min(tool_counts)}, "
                  f"max={max(tool_counts)}, avg={sum(tool_counts)/len(tool_counts):.1f}")


if __name__ == "__main__":
    main()
