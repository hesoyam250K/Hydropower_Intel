"""Turbine rotational dynamics and electromechanical generator modeling.

Models:
- Newton's rotational law: J * d(omega)/dt = T_mech - T_elec - D_damping * (omega - omega_0)
- Part-load efficiency variation
- Electrical frequency and grid coupling
"""

import math
from dataclasses import dataclass
from typing import Tuple

from src.engine.turbine import calculate_part_load_efficiency


WATER_DENSITY = 1000.0
G_STANDARD = 9.81


@dataclass
class TurbineGeneratorParams:
    """Mechanical and electrical parameters for turbine-generator set."""
    turbine_type: str = "Francis Reaction Turbine"
    rated_speed_rpm: float = 1000.0  # Synchronous speed (RPM)
    moment_of_inertia_kg_m2: float = 250.0  # Polar moment of inertia J (kg*m^2)
    damping_factor: float = 5.0  # Self-regulation damping D (N*m*s/rad)
    generator_efficiency: float = 0.94  # Generator electromagnetic efficiency
    peak_hydraulic_efficiency: float = 0.90  # Peak turbine efficiency
    pole_pairs: int = 3  # For 1000 RPM at 50 Hz: p = (120*50)/(2*1000) = 3


def rpm_to_rad_s(rpm: float) -> float:
    """Converts revolutions per minute to radians per second: omega = 2*pi*N / 60."""
    return (2.0 * math.pi * rpm) / 60.0


def rad_s_to_rpm(omega: float) -> float:
    """Converts radians per second to revolutions per minute: N = 60*omega / (2*pi)."""
    return (60.0 * omega) / (2.0 * math.pi)


def calculate_electrical_frequency(omega: float, pole_pairs: int = 3) -> float:
    """Calculates grid electrical frequency in Hertz: f = (omega * pole_pairs) / (2 * pi)."""
    return (omega * pole_pairs) / (2.0 * math.pi)


def turbine_generator_derivatives(
    omega_rad_s: float,
    flow_m3s: float,
    net_head_m: float,
    electrical_load_kw: float,
    rated_flow_m3s: float,
    params: TurbineGeneratorParams,
    density: float = WATER_DENSITY,
    g: float = G_STANDARD
) -> Tuple[float, float, float, float, float]:
    """Computes rotational acceleration d(omega)/dt and performance state.

    Returns:
    - d_omega_dt (rad/s^2)
    - mechanical_power_kw (kW)
    - electrical_power_output_kw (kW)
    - mechanical_torque_nm (N*m)
    - electrical_frequency_hz (Hz)
    """
    safe_omega = max(1.0, omega_rad_s)
    sync_omega = rpm_to_rad_s(params.rated_speed_rpm)

    # 1. Hydraulic input power
    hydraulic_power_kw = (density * g * max(0.0, flow_m3s) * max(0.0, net_head_m)) / 1000.0

    # 2. Dynamic turbine part-load efficiency
    flow_ratio = flow_m3s / max(0.01, rated_flow_m3s) if rated_flow_m3s > 0 else 1.0
    turb_eff = calculate_part_load_efficiency(
        params.turbine_type, flow_ratio, params.peak_hydraulic_efficiency
    )

    # Speed factor derating (off-synchronous speed penalty)
    speed_ratio = safe_omega / sync_omega
    speed_factor = max(0.2, 1.0 - 0.5 * ((1.0 - speed_ratio) ** 2))
    overall_turb_eff = turb_eff * speed_factor

    # 3. Mechanical shaft power & torque
    mech_power_kw = hydraulic_power_kw * overall_turb_eff
    mech_power_watts = mech_power_kw * 1000.0
    torque_mech = mech_power_watts / safe_omega

    # 4. Electrical load power & torque
    # If grid-connected, electrical load is dictated by demand; if isolated, matches load
    elec_load_watts = electrical_load_kw * 1000.0
    elec_gen_power_kw = mech_power_kw * params.generator_efficiency
    torque_elec = elec_load_watts / safe_omega

    # 5. Damping torque
    torque_damping = params.damping_factor * (safe_omega - sync_omega)

    # 6. Rotational momentum balance: J * d(omega)/dt = T_m - T_e - T_d
    j = max(1.0, params.moment_of_inertia_kg_m2)
    d_omega_dt = (torque_mech - torque_elec - torque_damping) / j

    freq_hz = calculate_electrical_frequency(safe_omega, params.pole_pairs)

    return d_omega_dt, mech_power_kw, elec_gen_power_kw, torque_mech, freq_hz
