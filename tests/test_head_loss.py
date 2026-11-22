"""Unit tests for Darcy-Weisbach and Hazen-Williams head loss calculations."""

import pytest
import math
from src.engine.head_loss import (
    calculate_flow_velocity,
    calculate_reynolds_number,
    solve_darcy_friction_factor,
    calculate_darcy_weisbach_loss,
    calculate_hazen_williams_loss,
)


def test_flow_velocity_and_area():
    """Verifies continuity equation v = 4Q / (pi * D^2)."""
    # D = 0.5 m, Q = 0.5 m^3/s -> Area = pi * 0.25 / 4 = 0.19635 m^2 -> v = 0.5 / 0.19635 = 2.546 m/s
    area, velocity = calculate_flow_velocity(0.5, 0.5)
    expected_area = math.pi * (0.5 ** 2) / 4.0
    expected_velocity = 0.5 / expected_area

    assert area == pytest.approx(expected_area, rel=1e-5)
    assert velocity == pytest.approx(expected_velocity, rel=1e-5)

    with pytest.raises(ValueError):
        calculate_flow_velocity(0.5, 0.0)


def test_reynolds_laminar_and_turbulent():
    """Verifies Reynolds number and laminar friction factor f = 64 / Re."""
    # Laminar check
    re_laminar = 1000.0
    f_laminar = solve_darcy_friction_factor(re_laminar, 0.001)
    assert f_laminar == pytest.approx(64.0 / 1000.0, rel=1e-5)

    # Turbulent check: smooth pipe, Re = 100,000
    re_turbulent = 1e5
    f_turbulent = solve_darcy_friction_factor(re_turbulent, 0.0001)
    # Typical f for Re = 1e5 is around 0.018 - 0.022
    assert 0.015 < f_turbulent < 0.030


def test_darcy_weisbach_pipe_loss():
    """Verifies Darcy-Weisbach head loss with known parameters."""
    flow = 0.2  # m^3/s
    gross_head = 50.0  # m
    diameter = 0.3  # m
    length = 100.0  # m
    roughness = 0.045  # mm (welded steel)

    breakdown = calculate_darcy_weisbach_loss(
        flow_m3s=flow,
        gross_head_m=gross_head,
        pipe_diameter_m=diameter,
        pipe_length_m=length,
        roughness_mm=roughness,
        minor_fittings=[("bend_90_standard", 2), ("entrance_flush", 1)],
    )

    assert breakdown.flow_velocity_mps > 0
    assert breakdown.friction_factor > 0
    assert breakdown.friction_loss_m > 0
    assert breakdown.minor_losses_m > 0
    assert breakdown.total_head_loss_m == pytest.approx(
        breakdown.friction_loss_m + breakdown.minor_losses_m, rel=1e-5
    )


def test_hazen_williams_calculation():
    """Verifies Hazen-Williams metric head loss calculation."""
    # hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)
    flow = 0.1  # m3/s
    length = 500.0  # m
    diameter = 0.25  # m
    c = 130.0

    expected_hf = 10.67 * length * (flow ** 1.852) / ((c ** 1.852) * (diameter ** 4.870))

    breakdown = calculate_hazen_williams_loss(
        flow_m3s=flow,
        gross_head_m=80.0,
        pipe_diameter_m=diameter,
        pipe_length_m=length,
        c_factor=c,
    )

    assert breakdown.friction_loss_m == pytest.approx(expected_hf, rel=1e-4)
    assert breakdown.total_head_loss_m == pytest.approx(expected_hf, rel=1e-4)
