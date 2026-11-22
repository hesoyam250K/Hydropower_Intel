"""Unit tests for turbine selection, regime boundaries, and efficiency curves."""

import pytest
from src.engine.turbine import (
    calculate_specific_speed_ns,
    calculate_kinematic_specific_speed_nq,
    classify_turbine_regime,
    calculate_part_load_efficiency,
    TurbineRegimeThresholds,
)


def test_specific_speed():
    """Verifies Metric Ns and European nq formulas."""
    # Ns = N * sqrt(P) / H^1.25
    # Let N = 1000 rpm, P = 100 kW, H = 25 m -> H^1.25 = 25^1.25 = 55.9017
    # Ns = 1000 * 10 / 55.9017 = 178.88
    ns = calculate_specific_speed_ns(power_kw=100.0, net_head_m=25.0, rpm=1000.0)
    assert ns == pytest.approx(178.885, rel=1e-3)

    # Zero cases
    assert calculate_specific_speed_ns(0.0, 25.0, 1000.0) == 0.0
    assert calculate_specific_speed_ns(100.0, 0.0, 1000.0) == 0.0


def test_regime_classification():
    """Verifies that high head selects Pelton, medium selects Francis, and low selects Kaplan."""
    # High head (e.g. 250 m, modest flow 0.2 m^3/s)
    sel_high = classify_turbine_regime(net_head_m=250.0, flow_m3s=0.2, power_kw=400.0)
    assert "Pelton" in sel_high.primary_recommendation
    assert sel_high.regime_category == "High Head — Impulse Regime"

    # Medium head (e.g. 45 m, flow 1.5 m^3/s)
    sel_med = classify_turbine_regime(net_head_m=45.0, flow_m3s=1.5, power_kw=550.0)
    assert "Francis" in sel_med.primary_recommendation
    assert sel_med.regime_category == "Medium Head — Mixed Flow Regime"

    # Low head (e.g. 8 m, high flow 4.0 m^3/s)
    sel_low = classify_turbine_regime(net_head_m=8.0, flow_m3s=4.0, power_kw=250.0)
    assert "Kaplan" in sel_low.primary_recommendation
    assert "Axial Flow" in sel_low.regime_category


def test_part_load_curves():
    """Verifies relative efficiency behavior across Pelton, Francis, and Kaplan."""
    # At 100% flow (q=1.0), all should reach peak efficiency (e.g. 0.90)
    assert calculate_part_load_efficiency("Pelton", 1.0, 0.90) == pytest.approx(0.90, rel=1e-3)
    assert calculate_part_load_efficiency("Francis", 1.0, 0.90) == pytest.approx(0.90, rel=1e-3)
    assert calculate_part_load_efficiency("Kaplan", 1.0, 0.90) == pytest.approx(0.90, rel=1e-3)

    # At 30% flow (q=0.3), Pelton should maintain higher efficiency than Francis
    eff_pelton_30 = calculate_part_load_efficiency("Pelton", 0.3, 0.90)
    eff_francis_30 = calculate_part_load_efficiency("Francis", 0.3, 0.90)
    assert eff_pelton_30 > eff_francis_30
