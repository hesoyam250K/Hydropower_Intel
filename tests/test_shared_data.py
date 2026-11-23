"""Unit tests for SharedEngineeringContext and cross-module data integration."""

import pytest
from src.engine.shared_data import (
    SharedEngineeringContext,
    build_shared_context_from_calc,
)
from src.engine.hydropower import calculate_comprehensive_hydropower
from src.hydrothermal.heat_transfer import analyze_hydrothermal_system
from src.hydrothermal.structural import analyze_thermal_structural_behavior


def test_shared_context_default():
    """Verifies default SharedEngineeringContext instantiates with valid parameters."""
    ctx = SharedEngineeringContext()
    assert ctx.flow_lps == 1000.0
    assert ctx.gross_head_m == 25.0
    assert ctx.data_provenance == "CALCULATED_DESIGN"
    d = ctx.to_dict()
    assert isinstance(d, dict)
    assert d["flow_lps"] == 1000.0


def test_shared_context_from_calculation():
    """Verifies that shared context accurately captures hydraulic and hydrothermal outputs."""
    calc = calculate_comprehensive_hydropower(
        flow_lps=1200.0,
        gross_head_m=35.0,
        loss_method="manual",
        manual_head_loss_m=2.0,
        efficiency=0.85
    )
    th = analyze_hydrothermal_system(
        flow_lps=1200.0,
        inlet_temp_c=14.0,
        ambient_air_temp_c=-2.0,
        u_value_w_m2k=4.0,
        heat_transfer_area_m2=200.0,
        wall_thickness_m=0.30
    )
    st = analyze_thermal_structural_behavior(
        initial_length_m=60.0,
        structure_temp_c=th.mean_fluid_temp_c,
        datum_temp_c=15.0,
        restraint_factor=0.5
    )

    ctx = build_shared_context_from_calc(
        calc=calc,
        project={"name": "Cascade Test Hydro", "id": 42},
        thermal_res=th,
        struct_res=st
    )

    assert ctx.project_name == "Cascade Test Hydro"
    assert ctx.project_id == 42
    assert ctx.flow_lps == 1200.0
    assert ctx.net_head_m == 33.0
    assert ctx.electrical_power_kw > 0
    assert ctx.water_inlet_temp_c == 14.0
    assert ctx.fluid_thermal_transfer_kw > 0
    assert ctx.thermal_expansion_mm != 0.0
