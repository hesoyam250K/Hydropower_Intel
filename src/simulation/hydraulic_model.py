"""Hydraulic transient and dynamic flow modeling.

Models time-dependent water movement in hydropower penstocks:
- Water column inertia and momentum: (L/gA) * dQ/dt = H_res - H_tail - hf - H_turb
- Reservoir mass conservation: dZ_res/dt = (Q_inflow - Q) / A_res
- Penstock friction and dynamic head losses.
"""

import math
from dataclasses import dataclass
from typing import Tuple


G_STANDARD = 9.81
WATER_DENSITY = 1000.0


@dataclass
class HydraulicPlantParams:
    """Physical parameters for dynamic hydraulic plant simulation."""
    reservoir_area_m2: float = 10000.0  # Surface area of reservoir / forebay
    initial_water_level_m: float = 30.0  # Reservoir surface level relative to turbine
    tailwater_level_m: float = 0.0  # Tailrace level
    pipe_length_m: float = 150.0  # Penstock length L
    pipe_diameter_m: float = 0.50  # Penstock internal diameter D
    pipe_roughness_mm: float = 0.045  # Steel roughness epsilon
    rated_flow_m3s: float = 1.0  # Design flow Q_rated
    nozzle_area_equivalent_m2: float = 0.035  # Effective turbine valve/nozzle flow area


def compute_penstock_friction_head(
    flow_m3s: float,
    length_m: float,
    diameter_m: float,
    roughness_mm: float,
    g: float = G_STANDARD
) -> float:
    """Calculates instantaneous Darcy-Weisbach friction head loss with signed flow direction."""
    if diameter_m <= 0:
        return 0.0
    area = math.pi * (diameter_m ** 2) / 4.0
    velocity = flow_m3s / area
    v_abs = abs(velocity)
    if v_abs < 1e-6:
        return 0.0

    # Explicit Swamee-Jain friction factor for fast continuous ODE evaluation
    nu = 1.004e-6
    reynolds = max(100.0, (v_abs * diameter_m) / nu)
    rel_roughness = (roughness_mm / 1000.0) / diameter_m

    if reynolds <= 2000.0:
        f = 64.0 / reynolds
    else:
        log_term = (rel_roughness / 3.7) + (5.74 / (reynolds ** 0.9))
        f = 0.25 / (math.log10(max(log_term, 1e-12)) ** 2)

    hf = f * (length_m / diameter_m) * (velocity * v_abs) / (2.0 * g)
    return hf


def compute_turbine_head_drop(
    flow_m3s: float,
    gate_opening: float,
    rated_flow_m3s: float,
    rated_head_m: float
) -> float:
    """Calculates effective head consumed across the turbine runner/nozzle:

    H_turb = H_rated * (Q / (a * Q_rated))^2
    Where 'a' is guide vane / needle gate opening fraction (0 < a <= 1.0).
    """
    effective_gate = max(0.01, min(1.0, gate_opening))
    if abs(flow_m3s) < 1e-6:
        return 0.0
    q_ratio = flow_m3s / (effective_gate * rated_flow_m3s)
    # Quadratic orifice / nozzle pressure drop
    h_turb = rated_head_m * (q_ratio * abs(q_ratio))
    return h_turb


def hydraulic_derivatives(
    t: float,
    flow_m3s: float,
    water_level_m: float,
    gate_opening: float,
    inflow_m3s: float,
    params: HydraulicPlantParams,
    g: float = G_STANDARD
) -> Tuple[float, float, float]:
    """Computes time derivatives [dQ/dt, dZ_res/dt] and effective net head:

    1. Mass conservation: dZ_res/dt = (Q_inflow - Q) / A_reservoir
    2. Momentum balance: dQ/dt = (g * A / L) * (H_gross - H_friction - H_turbine)
    """
    pipe_area = math.pi * (params.pipe_diameter_m ** 2) / 4.0
    gross_head = max(0.0, water_level_m - params.tailwater_level_m)

    # Reservoir level rate of change
    dz_dt = (inflow_m3s - flow_m3s) / max(100.0, params.reservoir_area_m2)

    # Friction loss
    h_fric = compute_penstock_friction_head(
        flow_m3s, params.pipe_length_m, params.pipe_diameter_m, params.pipe_roughness_mm, g
    )

    # Turbine runner / nozzle backpressure
    h_turb = compute_turbine_head_drop(
        flow_m3s, gate_opening, params.rated_flow_m3s, gross_head
    )

    # Net head driving the turbine runner
    net_head = max(0.0, gross_head - abs(h_fric))

    # Momentum derivative: dQ/dt = (g * A / L) * (Gross_head - friction - turbine_drop)
    # Inertial coefficient L / (g * A)
    inertia_coeff = params.pipe_length_m / (g * pipe_area)
    dq_dt = (gross_head - h_fric - h_turb) / max(0.01, inertia_coeff)

    return dq_dt, dz_dt, net_head
