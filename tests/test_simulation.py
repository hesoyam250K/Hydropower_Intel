"""Unit tests for dynamic hydraulic and turbine simulation models."""

import pytest
import numpy as np
from src.simulation.scenarios import (
    run_dynamic_simulation,
    SimulationConfig,
)
from src.simulation.hydraulic_model import (
    HydraulicPlantParams,
    compute_penstock_friction_head,
)
from src.simulation.turbine_model import (
    TurbineGeneratorParams,
    calculate_electrical_frequency,
)
from src.simulation.control_system import HydroGovernor, GovernorParams


def test_hydraulic_friction_head():
    """Verifies penstock friction calculation within simulation."""
    hf = compute_penstock_friction_head(
        flow_m3s=1.0,
        length_m=100.0,
        diameter_m=0.5,
        roughness_mm=0.045
    )
    assert hf > 0.0
    assert hf < 10.0  # Reasonable range for 100m penstock at ~5 m/s


def test_frequency_calculation():
    """Verifies electrical frequency conversion for 1000 RPM 3-pole-pair generator."""
    # omega = 2 * pi * 1000 / 60 = 104.72 rad/s
    omega = (2.0 * np.pi * 1000.0) / 60.0
    freq = calculate_electrical_frequency(omega, pole_pairs=3)
    assert freq == pytest.approx(50.0, rel=1e-3)


def test_governor_regulation():
    """Verifies that the governor reduces gate opening when speed rises above target."""
    gov = HydroGovernor(GovernorParams(), initial_gate=0.80)
    target_omega = 100.0
    overspeed_omega = 110.0  # Speed is high

    # In automatic mode, governor should throttle back gate
    new_gate = gov.update(
        target_omega=target_omega,
        current_omega=overspeed_omega,
        dt=0.1,
        is_auto=True
    )
    assert new_gate < 0.80


def test_steady_state_simulation():
    """Tests baseline steady-state simulation execution."""
    cfg = SimulationConfig(
        duration_s=10.0,
        dt=0.1,
        scenario_type="steady_state",
    )
    res = run_dynamic_simulation(config=cfg)

    assert len(res.time_s) == 101
    assert res.electrical_power_kw[0] > 0
    assert res.total_energy_kwh > 0
    assert res.scenario_name == "Steady-State Baseline"
    assert len(res.assumptions) >= 4


def test_load_rejection_transient():
    """Verifies that sudden electrical load drop triggers runner overspeed."""
    cfg = SimulationConfig(
        duration_s=15.0,
        dt=0.05,
        scenario_type="load_rejection",
        event_time_s=5.0,
        nominal_electrical_load_kw=150.0,
    )
    res = run_dynamic_simulation(config=cfg)

    # After t=5s, speed should experience a transient rise
    assert res.max_overspeed_pct > 0.0
    assert res.peak_speed_rpm > 1000.0
