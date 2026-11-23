"""Unit tests for 3D procedural geometry creation, field color mapping, and GLB export."""

import pytest
import trimesh
from src.geometry.mesh_builder import PlantGeometryBuilder
from src.geometry.exporter import (
    build_scene_and_export_glb,
    apply_engineering_visualization_fields,
    map_scalar_to_thermal_color,
    map_scalar_to_stress_color,
)
from src.engine.shared_data import SharedEngineeringContext


def test_geometry_builder_components():
    """Verifies that the builder constructs all required civil and mechanical solids."""
    builder = PlantGeometryBuilder(gross_head_m=30.0, pipe_diameter_m=0.6, include_bridge=True)
    comps = builder.build_all_components()

    # Verify hydropower components
    assert "reservoir_water" in comps
    assert "dam_structure" in comps
    assert "intake_gate" in comps
    assert "penstock_pipe" in comps
    assert "powerhouse_casing" in comps
    assert "turbine_runner" in comps
    assert "generator_stator" in comps
    assert "draft_tube_tailrace" in comps

    # Verify hydrothermal bridge components
    assert "bridge_deck" in comps
    assert "conduit_pipe" in comps
    assert "bridge_piers" in comps
    assert "expansion_joints" in comps
    assert "thermal_bridge_regions" in comps

    # Verify mesh geometry validity
    for cid, comp in comps.items():
        assert len(comp.mesh.vertices) > 0
        assert len(comp.mesh.faces) > 0


def test_geometry_builder_hydropower_only():
    """Verifies that bridge components are omitted when include_bridge is False."""
    builder = PlantGeometryBuilder(include_bridge=False)
    comps = builder.build_all_components()
    assert "reservoir_water" in comps
    assert "dam_structure" in comps
    assert "bridge_deck" not in comps
    assert "conduit_pipe" not in comps


def test_colormap_functions():
    """Verifies thermal and stress colormap functions return valid 4-tuple RGBA values."""
    c_cold = map_scalar_to_thermal_color(-10.0, -10.0, 30.0)
    assert len(c_cold) == 4
    assert c_cold[2] == 255  # Blue

    c_hot = map_scalar_to_thermal_color(30.0, -10.0, 30.0)
    assert len(c_hot) == 4
    assert c_hot[0] == 255  # Red

    c_stress_safe = map_scalar_to_stress_color(5.0, 30.0)
    assert len(c_stress_safe) == 4
    assert c_stress_safe[1] > 200  # Green dominant


def test_glb_export():
    """Verifies that build_scene_and_export_glb generates a valid binary GLTF (GLB)."""
    ctx = SharedEngineeringContext(gross_head_m=28.0)
    glb_bytes = build_scene_and_export_glb(context=ctx, mode="FLOW", output_path=None)

    assert isinstance(glb_bytes, bytes)
    assert len(glb_bytes) > 2000
    # Valid GLB header starts with magic bytes 'glTF' (0x46546C67 in little endian)
    assert glb_bytes[:4] == b"glTF"
