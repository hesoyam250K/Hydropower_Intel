"""Convective and conductive heat transfer calculations for hydrothermal bridges and conduits.

Implements:
1. Fluid convective thermal transport: Q_thermal = m_dot * cp * (Tin - Tout)
2. Conductive thermal bridge loss: Q_cond = U * A * (Tfluid - Tambient)
3. 1D Fourier conduction heat flux: q = -k * dT/dx
4. Analytical temperature profile and predicted outlet conditions.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.hydrothermal.materials import EngineeringMaterial, get_material
from src.hydrothermal.boundary_conditions import HydrothermalBoundaryConditions
from src.hydrothermal.validation import validate_hydrothermal_inputs, HydrothermalValidationError


WATER_SPECIFIC_HEAT = 4184.0  # J/kg·K (Standard freshwater at 15-20°C)
WATER_DENSITY = 1000.0         # kg/m³
STANDARD_GRAVITY = 9.81        # m/s²


@dataclass
class HydrothermalHeatTransferResult:
    """Complete quantitative results of hydrothermal heat transfer analysis."""
    mass_flow_rate_kg_s: float
    volumetric_flow_m3s: float
    inlet_temp_c: float
    outlet_temp_c: float
    mean_fluid_temp_c: float
    ambient_air_temp_c: float
    delta_t_fluid_c: float             # Tin - Tout (positive = fluid cooled)
    fluid_thermal_transfer_w: float    # Watts
    fluid_thermal_transfer_kw: float   # Kilowatts
    thermal_bridge_loss_w: float       # U-value method (Watts)
    thermal_bridge_loss_kw: float      # U-value method (Kilowatts)
    fourier_heat_flux_w_m2: float      # 1D Fourier heat flux (W/m²)
    fourier_total_conduction_kw: float # 1D Fourier total loss (kW)
    thermal_loss_percentage: float     # Percentage of available thermal energy transferred
    heat_transfer_mode: str            # 'Heat Loss to Environment' or 'Heat Gain from Environment'
    formula_substitutions: List[Dict[str, str]]


def calculate_mass_flow_rate(flow_m3s: float, density_kg_m3: float = WATER_DENSITY) -> float:
    """Calculates mass flow rate: m_dot = rho * Q (kg/s)."""
    if flow_m3s < 0:
        raise HydrothermalValidationError(f"Flow rate cannot be negative: {flow_m3s}")
    return density_kg_m3 * flow_m3s


def calculate_convective_fluid_heat(
    mass_flow_kg_s: float,
    inlet_temp_c: float,
    outlet_temp_c: float,
    cp_j_kgk: float = WATER_SPECIFIC_HEAT
) -> Tuple[float, float]:
    """Calculates convective heat transfer in fluid:

    Q_thermal = m_dot * cp * (Tin - Tout)

    Returns:
    - (Q_thermal_watts, Q_thermal_kw)
    Preserves sign:
    - Positive: Heat transferred OUT of fluid (fluid cools)
    - Negative: Heat transferred INTO fluid (fluid warms)
    """
    delta_t = inlet_temp_c - outlet_temp_c
    q_watts = mass_flow_kg_s * cp_j_kgk * delta_t
    return q_watts, q_watts / 1000.0


def calculate_conductive_bridge_loss(
    u_value_w_m2k: float,
    area_m2: float,
    fluid_temp_c: float,
    ambient_temp_c: float
) -> Tuple[float, float]:
    """Calculates conductive thermal bridge loss:

    Q_cond = U * A * (T_fluid - T_ambient)

    Returns (Q_cond_watts, Q_cond_kw).
    """
    delta_t = fluid_temp_c - ambient_temp_c
    q_watts = u_value_w_m2k * area_m2 * delta_t
    return q_watts, q_watts / 1000.0


def calculate_fourier_conduction(
    thermal_conductivity_w_mk: float,
    wall_thickness_m: float,
    area_m2: float,
    inner_temp_c: float,
    outer_temp_c: float
) -> Tuple[float, float, float]:
    """Calculates 1D steady-state Fourier heat conduction:

    q = -k * grad(T) = k * (T_inner - T_outer) / t_wall

    Returns:
    - heat_flux_w_m2 (W/m²)
    - total_conduction_watts (W)
    - total_conduction_kw (kW)
    """
    if wall_thickness_m <= 0:
        raise HydrothermalValidationError("Wall thickness must be strictly positive.")
    grad_t = (inner_temp_c - outer_temp_c) / wall_thickness_m
    heat_flux = thermal_conductivity_w_mk * grad_t
    total_watts = heat_flux * area_m2
    return heat_flux, total_watts, total_watts / 1000.0


def predict_outlet_temperature(
    inlet_temp_c: float,
    ambient_temp_c: float,
    mass_flow_kg_s: float,
    u_value_w_m2k: float,
    area_m2: float,
    cp_j_kgk: float = WATER_SPECIFIC_HEAT
) -> float:
    """Predicts outlet temperature from 1D energy balance (NTU heat exchanger model):

    Tout = Tambient + (Tin - Tambient) * exp(-UA / (m_dot * cp))
    """
    if mass_flow_kg_s <= 1e-6:
        # Zero flow: water stagnates and reaches thermal equilibrium with ambient air
        return ambient_temp_c

    capacitance_rate = mass_flow_kg_s * cp_j_kgk
    ua = u_value_w_m2k * area_m2
    exponent = -ua / capacitance_rate
    t_out = ambient_temp_c + (inlet_temp_c - ambient_temp_c) * math.exp(exponent)
    return t_out


def analyze_hydrothermal_system(
    flow_lps: float,
    inlet_temp_c: float,
    ambient_air_temp_c: float,
    u_value_w_m2k: float,
    heat_transfer_area_m2: float,
    wall_thickness_m: float,
    outlet_temp_c: Optional[float] = None,
    material: Optional[EngineeringMaterial] = None,
    density_kg_m3: float = WATER_DENSITY,
    gravity_m_s2: float = STANDARD_GRAVITY,
    specific_heat_j_kgk: float = WATER_SPECIFIC_HEAT
) -> HydrothermalHeatTransferResult:
    """Complete, self-contained hydrothermal energy analysis.

    Accommodates explicit parameters for density, gravity, specific heat,
    heat-transfer area, and ambient temperatures without undefined variables.
    """
    mat = material or get_material("reinforced_concrete")
    q_m3s = flow_lps / 1000.0
    mass_flow = calculate_mass_flow_rate(q_m3s, density_kg_m3)

    # Determine outlet condition
    if outlet_temp_c is None:
        t_out = predict_outlet_temperature(
            inlet_temp_c=inlet_temp_c,
            ambient_temp_c=ambient_air_temp_c,
            mass_flow_kg_s=mass_flow,
            u_value_w_m2k=u_value_w_m2k,
            area_m2=heat_transfer_area_m2,
            cp_j_kgk=specific_heat_j_kgk
        )
    else:
        t_out = outlet_temp_c

    t_avg = 0.5 * (inlet_temp_c + t_out)
    delta_t = inlet_temp_c - t_out

    # Convective fluid thermal transfer: Q = m_dot * cp * (Tin - Tout)
    q_conv_w, q_conv_kw = calculate_convective_fluid_heat(
        mass_flow_kg_s=mass_flow,
        inlet_temp_c=inlet_temp_c,
        outlet_temp_c=t_out,
        cp_j_kgk=specific_heat_j_kgk
    )

    # Conductive bridge loss: Q_cond = U * A * (T_avg - T_amb)
    q_bridge_w, q_bridge_kw = calculate_conductive_bridge_loss(
        u_value_w_m2k=u_value_w_m2k,
        area_m2=heat_transfer_area_m2,
        fluid_temp_c=t_avg,
        ambient_temp_c=ambient_air_temp_c
    )

    # Fourier 1D wall conduction
    flux_w_m2, fourier_w, fourier_kw = calculate_fourier_conduction(
        thermal_conductivity_w_mk=mat.thermal_conductivity_w_mk,
        wall_thickness_m=wall_thickness_m,
        area_m2=heat_transfer_area_m2,
        inner_temp_c=t_avg,
        outer_temp_c=ambient_air_temp_c
    )

    # Categorize mode
    if delta_t >= 0:
        mode = "Heat Loss to Environment (Water cools along span)"
    else:
        mode = "Heat Gain from Environment (Water warms along span)"

    # Total reference convective thermal capacity rate
    ref_capacitance = mass_flow * specific_heat_j_kgk
    thermal_loss_pct = (abs(q_conv_w) / (ref_capacitance * max(0.1, abs(inlet_temp_c - ambient_air_temp_c)))) * 100.0 if ref_capacitance > 0 else 0.0

    steps = [
        {
            "step": "1. Fluid Mass Flow Rate",
            "formula": "ṁ = ρ × Q",
            "substitution": f"{density_kg_m3:.1f} kg/m³ × {q_m3s:.4f} m³/s",
            "result": f"{mass_flow:.2f} kg/s",
        },
        {
            "step": "2. Convective Fluid Thermal Transfer",
            "formula": "Q_thermal = ṁ × cp × (T_in - T_out)",
            "substitution": f"{mass_flow:.2f} kg/s × {specific_heat_j_kgk:.1f} J/kg·K × ({inlet_temp_c:.2f}°C - {t_out:.2f}°C)",
            "result": f"{q_conv_kw:,.2f} kW ({q_conv_w:,.1f} W)",
        },
        {
            "step": "3. Conductive Thermal Bridge Loss (U-Value Method)",
            "formula": "Q_cond = U × A × (T_fluid_avg - T_ambient)",
            "substitution": f"{u_value_w_m2k:.2f} W/m²·K × {heat_transfer_area_m2:.1f} m² × ({t_avg:.2f}°C - {ambient_air_temp_c:.2f}°C)",
            "result": f"{q_bridge_kw:,.2f} kW ({q_bridge_w:,.1f} W)",
        },
        {
            "step": "4. Fourier 1D Wall Conduction",
            "formula": "q = -k × ∇T = k × (T_inner - T_outer) / t_wall",
            "substitution": f"{mat.thermal_conductivity_w_mk:.2f} W/m·K × ({t_avg:.2f}°C - {ambient_air_temp_c:.2f}°C) / {wall_thickness_m:.3f} m",
            "result": f"{flux_w_m2:.2f} W/m² (Total: {fourier_kw:.2f} kW)",
        },
    ]

    return HydrothermalHeatTransferResult(
        mass_flow_rate_kg_s=mass_flow,
        volumetric_flow_m3s=q_m3s,
        inlet_temp_c=inlet_temp_c,
        outlet_temp_c=t_out,
        mean_fluid_temp_c=t_avg,
        ambient_air_temp_c=ambient_air_temp_c,
        delta_t_fluid_c=delta_t,
        fluid_thermal_transfer_w=q_conv_w,
        fluid_thermal_transfer_kw=q_conv_kw,
        thermal_bridge_loss_w=q_bridge_w,
        thermal_bridge_loss_kw=q_bridge_kw,
        fourier_heat_flux_w_m2=flux_w_m2,
        fourier_total_conduction_kw=fourier_kw,
        thermal_loss_percentage=min(100.0, thermal_loss_pct),
        heat_transfer_mode=mode,
        formula_substitutions=steps
    )
