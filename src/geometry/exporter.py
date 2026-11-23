"""Mesh exporter and visualization field coloring for GLTF/GLB/OBJ formats."""

import io
import os
from typing import Dict, List, Optional, Tuple
import numpy as np
import trimesh

from src.geometry.mesh_builder import Component3D, PlantGeometryBuilder
from src.engine.shared_data import SharedEngineeringContext


DEFAULT_GLB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "models",
    "hydropower_bridge_model.glb"
)


def map_scalar_to_thermal_color(val: float, v_min: float, v_max: float) -> Tuple[int, int, int, int]:
    """Maps a scalar temperature (°C) to an intuitive cold-to-hot colormap (Blue -> Cyan -> Yellow -> Red)."""
    norm = max(0.0, min(1.0, (val - v_min) / max(0.01, v_max - v_min)))
    if norm < 0.25:
        # Deep Blue to Cyan
        r = 0
        g = int(norm * 4 * 255)
        b = 255
    elif norm < 0.50:
        # Cyan to Green
        r = 0
        g = 255
        b = int((1.0 - (norm - 0.25) * 4) * 255)
    elif norm < 0.75:
        # Green to Yellow
        r = int((norm - 0.50) * 4 * 255)
        g = 255
        b = 0
    else:
        # Yellow to Red
        r = 255
        g = int((1.0 - (norm - 0.75) * 4) * 255)
        b = 0
    return (r, g, b, 255)


def map_scalar_to_stress_color(stress_mpa: float, allowable_mpa: float) -> Tuple[int, int, int, int]:
    """Maps structural stress to civil engineering safety colormap (Green -> Yellow -> Red)."""
    ratio = max(0.0, min(1.0, abs(stress_mpa) / max(1.0, allowable_mpa)))
    if ratio < 0.40:
        # Green to Amber
        r = int((ratio / 0.40) * 255)
        g = 220
        b = 30
    else:
        # Amber to Red
        r = 255
        g = int(max(0, (1.0 - (ratio - 0.40) / 0.60) * 200))
        b = 20
    return (r, g, b, 255)


def apply_engineering_visualization_fields(
    components: Dict[str, Component3D],
    context: Optional[SharedEngineeringContext] = None,
    mode: str = "FLOW"  # 'FLOW', 'THERMAL', 'STRUCTURAL'
) -> Dict[str, Component3D]:
    """Applies engineering field colors to the mesh components based on active context."""
    ctx = context or SharedEngineeringContext()

    for comp_id, comp in components.items():
        mesh = comp.mesh.copy()
        n_faces = len(mesh.faces)
        color = comp.base_color_rgba

        if mode == "THERMAL":
            # Color by thermal field
            t_in = ctx.water_inlet_temp_c
            t_out = ctx.water_outlet_temp_c
            t_amb = ctx.ambient_air_temp_c
            t_min = min(t_amb, min(t_in, t_out)) - 2.0
            t_max = max(t_amb, max(t_in, t_out)) + 2.0

            if comp_id in ("reservoir_water", "draft_tube_tailrace"):
                color = map_scalar_to_thermal_color(t_in, t_min, t_max)
            elif comp_id == "conduit_pipe":
                # Hot hydrothermal conduit
                color = map_scalar_to_thermal_color(t_in, t_min, t_max)
            elif comp_id == "thermal_bridge_regions":
                # Thermal bridge contact zone
                t_mid = 0.5 * (t_in + t_amb)
                color = map_scalar_to_thermal_color(t_mid, t_min, t_max)
            elif comp_id in ("dam_structure", "bridge_deck", "bridge_piers"):
                # Structural solids exposed to ambient
                color = map_scalar_to_thermal_color(t_amb, t_min, t_max)

        elif mode == "STRUCTURAL":
            # Color by thermal stress / utilization
            stress = ctx.thermal_stress_mpa
            if comp_id == "thermal_bridge_regions":
                color = map_scalar_to_stress_color(stress * 1.5, 30.0)
            elif comp_id in ("bridge_deck", "bridge_piers"):
                color = map_scalar_to_stress_color(stress, 30.0)
            elif comp_id == "expansion_joints":
                color = (250, 204, 21, 255)  # Bright expansion yellow

        elif mode == "FLOW":
            # High-contrast flow visual mode
            if comp_id in ("reservoir_water", "penstock_pipe", "draft_tube_tailrace"):
                vel = ctx.water_velocity_mps
                # Color code velocity
                if vel > 3.5:
                    color = (239, 68, 68, 220)  # High velocity red
                elif vel > 1.5:
                    color = (14, 165, 233, 220)  # Nominal economic blue
                else:
                    color = (56, 189, 248, 180)  # Low velocity cyan

        # Apply uniform face color to Trimesh
        mesh.visual.face_colors = np.tile(color, (n_faces, 1))
        comp.mesh = mesh

    return components


def build_scene_and_export_glb(
    builder: Optional[PlantGeometryBuilder] = None,
    context: Optional[SharedEngineeringContext] = None,
    mode: str = "FLOW",
    output_path: Optional[str] = DEFAULT_GLB_PATH
) -> bytes:
    """Builds the 3D assembly, applies engineering fields, and exports GLB binary."""
    geom_builder = builder or PlantGeometryBuilder()
    components = geom_builder.build_all_components()
    colored_components = apply_engineering_visualization_fields(components, context, mode)

    # Assemble scene
    scene = trimesh.Scene()
    for comp_id, comp in colored_components.items():
        scene.add_geometry(comp.mesh, node_name=comp_id, geom_name=comp_id)

    # Export to GLB bytes
    glb_bytes = scene.export(file_type="glb")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(glb_bytes)

    return glb_bytes
