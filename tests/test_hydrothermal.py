"""Unit tests for the hydrothermal engineering analysis engine."""

import pytest
from src.hydrothermal.materials import get_material, MATERIAL_DATABASE
from src.hydrothermal.boundary_conditions import HydrothermalBoundaryConditions
from src.hydrothermal.validation import validate_hydrothermal_inputs
from src.hydrothermal.heat_transfer import (
    calculate_mass_flow_rate,
    calculate_convective_fluid_heat,
    calculate_conductive_bridge_loss,
    calculate_fourier_conduction,
    predict_outlet_temperature,
    analyze_hydrothermal_system,
)
from src.hydrothermal.structural import (
    calculate_thermal_expansion,
    calculate_thermal_stress,
    analyze_thermal_structural_behavior,
)
from src.hydrothermal.thermal_bridge import (
    WallLayer,
    analyze_composite_thermal_bridge,
)


def test_mass_flow_rate():
    """Verifies mass flow rate m_dot = rho * Q."""
    # 1.0 m3/s fresh water -> 1000 kg/s
    assert calculate_mass_flow_rate(1.0, 1000.0) == 1000.0
    assert calculate_mass_flow_rate(0.25, 1000.0) == 250.0

    with pytest.raises(Exception):
        calculate_mass_flow_rate(-0.5)


def test_convective_heat_transfer():
    """Verifies Q = m_dot * cp * (Tin - Tout) and sign preservation."""
    # 500 kg/s, cp = 4184 J/kg*K, Tin = 15°C, Tout = 10°C -> Cooling (+Q)
    # Q = 500 * 4184 * 5 = 10,460,000 W = 10,460 kW
    q_w, q_kw = calculate_convective_fluid_heat(
        mass_flow_kg_s=500.0,
        inlet_temp_c=15.0,
        outlet_temp_c=10.0,
        cp_j_kgk=4184.0
    )
    assert q_w == pytest.approx(10460000.0, rel=1e-4)
    assert q_kw == pytest.approx(10460.0, rel=1e-4)
    assert q_kw > 0  # Water lost heat

    # Warming (-Q)
    q_warm_w, q_warm_kw = calculate_convective_fluid_heat(
        mass_flow_kg_s=500.0,
        inlet_temp_c=10.0,
        outlet_temp_c=15.0,
        cp_j_kgk=4184.0
    )
    assert q_warm_kw < 0
    assert q_warm_kw == pytest.approx(-10460.0, rel=1e-4)


def test_conductive_bridge_loss():
    """Verifies Q_cond = U * A * (T_fluid - T_amb)."""
    # U = 4.0 W/m2K, A = 100 m2, T_fluid = 12°C, T_amb = -8°C (Delta T = 20 K)
    # Q = 4 * 100 * 20 = 8000 W = 8 kW
    q_w, q_kw = calculate_conductive_bridge_loss(4.0, 100.0, 12.0, -8.0)
    assert q_w == pytest.approx(8000.0, rel=1e-4)
    assert q_kw == pytest.approx(8.0, rel=1e-4)


def test_fourier_conduction():
    """Verifies Fourier 1D conduction: q = k * DeltaT / t_wall."""
    # k = 1.8 W/mK, t_wall = 0.36 m, A = 100 m2, DeltaT = 10 K
    # q = 1.8 * 10 / 0.36 = 50 W/m2 -> Q = 5000 W = 5.0 kW
    flux, q_w, q_kw = calculate_fourier_conduction(1.8, 0.36, 100.0, 15.0, 5.0)
    assert flux == pytest.approx(50.0, rel=1e-4)
    assert q_kw == pytest.approx(5.0, rel=1e-4)


def test_thermal_expansion():
    """Verifies DeltaL = alpha * L0 * DeltaT in m and mm."""
    # Concrete alpha = 1.0e-5 / K, L0 = 50 m, DeltaT = 20 K
    # DeltaL = 1.0e-5 * 50 * 20 = 0.010 m = 10.0 mm
    expansion_m = calculate_thermal_expansion(50.0, 1.0e-5, 20.0)
    assert expansion_m == pytest.approx(0.010, rel=1e-4)
    assert expansion_m * 1000.0 == pytest.approx(10.0, rel=1e-4)


def test_thermal_stress_restraint_conditions():
    """Verifies sigma = R * E * alpha * DeltaT across restraint factors."""
    # Concrete: E = 33,000 MPa, alpha = 1.0e-5, DeltaT = 15 K
    # E * alpha * DeltaT = 33000 * 1.0e-5 * 15 = 4.95 MPa
    e_mpa = 33000.0
    alpha = 1.0e-5
    dt = 15.0

    # Fully restrained (R = 1.0)
    sigma_fixed = calculate_thermal_stress(e_mpa, alpha, dt, restraint_factor=1.0)
    assert sigma_fixed == pytest.approx(4.95, rel=1e-3)

    # Semi-restrained (R = 0.5)
    sigma_semi = calculate_thermal_stress(e_mpa, alpha, dt, restraint_factor=0.5)
    assert sigma_semi == pytest.approx(2.475, rel=1e-3)

    # Free expansion joint (R = 0.0)
    sigma_free = calculate_thermal_stress(e_mpa, alpha, dt, restraint_factor=0.0)
    assert sigma_free == 0.0


def test_complete_hydrothermal_analysis():
    """Verifies analyze_hydrothermal_system with explicit parameters."""
    mat = get_material("reinforced_concrete")
    res = analyze_hydrothermal_system(
        flow_lps=1000.0,
        inlet_temp_c=12.0,
        ambient_air_temp_c=-5.0,
        u_value_w_m2k=4.0,
        heat_transfer_area_m2=150.0,
        wall_thickness_m=0.30,
        material=mat
    )
    assert res.mass_flow_rate_kg_s == 1000.0
    assert res.volumetric_flow_m3s == 1.0
    assert res.outlet_temp_c < res.inlet_temp_c  # Water cooled
    assert res.fluid_thermal_transfer_kw > 0
    assert len(res.formula_substitutions) == 4


def test_validation_rules():
    """Verifies that invalid thermal boundary inputs are correctly identified."""
    mat = get_material("structural_steel")

    # Valid
    bc_valid = HydrothermalBoundaryConditions()
    val_ok = validate_hydrothermal_inputs(bc_valid, mat)
    assert val_ok.is_valid is True

    # Negative length and negative U-value
    bc_invalid = HydrothermalBoundaryConditions(bridge_length_m=-10.0, u_value_w_m2k=-2.0)
    val_bad = validate_hydrothermal_inputs(bc_invalid, mat)
    assert val_bad.is_valid is False
    assert len(val_bad.errors) >= 2


def test_composite_thermal_bridge_insulation():
    """Verifies composite wall analysis and insulation benefits."""
    conc = get_material("reinforced_concrete")
    ins = get_material("polyurethane_insulation")

    # Uninsulated vs Insulated
    layers_uninsulated = [WallLayer(conc, 0.35)]
    layers_insulated = [WallLayer(conc, 0.35), WallLayer(ins, 0.05)]

    res_unins = analyze_composite_thermal_bridge(layers_uninsulated, 100.0, 15.0, -5.0)
    res_ins = analyze_composite_thermal_bridge(layers_insulated, 100.0, 15.0, -5.0)

    # Insulated wall should have substantially lower U-value and heat loss
    assert res_ins.composite_u_value_w_m2k < res_unins.composite_u_value_w_m2k
    assert res_ins.insulated_heat_loss_kw < res_unins.insulated_heat_loss_kw
    assert res_ins.annual_energy_saved_kwh > 0
