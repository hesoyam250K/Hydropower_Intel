"""Unit tests for core hydropower engineering formulas and reference verification."""

import pytest
from src.engine.hydropower import (
    calculate_hydropower,
    calculate_comprehensive_hydropower,
    flow_lps_to_m3s,
    flow_m3s_to_lps,
)
from src.engine.validation import HydraulicValidationError


def test_reference_hydropower_calculation():
    """Verifies the known reference calculation from engineering specifications:

    Flow = 1000 L/s
    Gross head = 20 m
    Head loss = 2 m
    Efficiency = 0.75
    Operating duration = 24 hours

    Expected:
    Net head = 18 m
    Flow = 1 m3/s
    Power = 132.435 kW
    Energy = 3178.44 kWh
    """
    res = calculate_hydropower(
        flow_lps=1000.0,
        gross_head_m=20.0,
        head_loss_m=2.0,
        efficiency=0.75,
        hours=24.0,
    )

    assert res["flow_m3s"] == pytest.approx(1.0, rel=1e-5)
    assert res["net_head_m"] == pytest.approx(18.0, rel=1e-5)
    assert res["power_kw"] == pytest.approx(132.435, rel=1e-4)
    assert res["energy_kwh"] == pytest.approx(3178.44, rel=1e-4)


def test_flow_conversions():
    """Tests conversions between L/s and m3/s."""
    assert flow_lps_to_m3s(1000.0) == 1.0
    assert flow_lps_to_m3s(250.0) == 0.25
    assert flow_m3s_to_lps(1.0) == 1000.0
    assert flow_m3s_to_lps(0.05) == 50.0

    with pytest.raises(HydraulicValidationError):
        flow_lps_to_m3s(-10.0)

    with pytest.raises(HydraulicValidationError):
        flow_m3s_to_lps(-0.1)


def test_zero_flow_and_head():
    """Verifies behavior when flow or head is zero."""
    res_zero_flow = calculate_hydropower(flow_lps=0.0, gross_head_m=50.0, efficiency=0.85)
    assert res_zero_flow["power_kw"] == 0.0
    assert res_zero_flow["energy_kwh"] == 0.0

    res_zero_head = calculate_hydropower(flow_lps=500.0, gross_head_m=0.0, efficiency=0.85)
    assert res_zero_head["power_kw"] == 0.0


def test_invalid_parameters():
    """Verifies that invalid physical inputs raise appropriate exceptions."""
    # Negative flow
    with pytest.raises(ValueError):
        calculate_hydropower(flow_lps=-100.0, gross_head_m=20.0)

    # Negative gross head
    with pytest.raises(ValueError):
        calculate_hydropower(flow_lps=500.0, gross_head_m=-20.0)

    # Efficiency out of bounds
    with pytest.raises(ValueError):
        calculate_hydropower(flow_lps=500.0, gross_head_m=20.0, efficiency=1.2)

    with pytest.raises(ValueError):
        calculate_hydropower(flow_lps=500.0, gross_head_m=20.0, efficiency=-0.1)

    # Negative head loss
    with pytest.raises(ValueError):
        calculate_hydropower(flow_lps=500.0, gross_head_m=20.0, head_loss_m=-2.0)


def test_comprehensive_hydropower_manual():
    """Tests the comprehensive calculation engine with manual head loss."""
    res = calculate_comprehensive_hydropower(
        flow_lps=1000.0,
        gross_head_m=20.0,
        loss_method="manual",
        manual_head_loss_m=2.0,
        efficiency=0.75,
        hours=24.0,
        capacity_factor=0.85,
    )

    assert res.flow_m3s == 1.0
    assert res.net_head_m == 18.0
    assert res.hydraulic_power_kw == pytest.approx(176.58, rel=1e-3)
    assert res.electrical_power_kw == pytest.approx(132.435, rel=1e-3)
    assert res.energy_kwh == pytest.approx(3178.44, rel=1e-3)
    assert len(res.substitution_steps) == 6
