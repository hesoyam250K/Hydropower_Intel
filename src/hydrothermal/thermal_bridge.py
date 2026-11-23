"""Thermal bridge modeling, composite wall insulation, and condensation risk analysis."""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.hydrothermal.materials import EngineeringMaterial, get_material


@dataclass
class WallLayer:
    """A single material layer in a composite conduit/bridge wall."""
    material: EngineeringMaterial
    thickness_m: float

    @property
    def thermal_resistance(self) -> float:
        """R-value of this individual layer: R = t / k (m²·K/W)."""
        return self.thickness_m / max(1e-5, self.material.thermal_conductivity_w_mk)


@dataclass
class ThermalBridgeAnalysisResult:
    """Comprehensive composite thermal bridge evaluation."""
    composite_u_value_w_m2k: float
    total_thermal_resistance_m2k_w: float
    uninsulated_heat_loss_kw: float
    insulated_heat_loss_kw: float
    annual_energy_saved_kwh: float
    linear_bridge_heat_loss_kw: float
    internal_surface_temp_c: float
    external_surface_temp_c: float
    condensation_risk: bool
    dew_point_temp_c: float
    hotspots: List[Dict[str, str]]


def calculate_dew_point(temperature_c: float, relative_humidity_pct: float = 75.0) -> float:
    """Calculates dew point temperature using Magnus-Tetens approximation."""
    rh = max(0.01, min(1.0, relative_humidity_pct / 100.0))
    a = 17.27
    b = 237.7
    alpha = ((a * temperature_c) / (b + temperature_c)) + math.log(rh)
    dew_point = (b * alpha) / (a - alpha)
    return round(dew_point, 1)


def analyze_composite_thermal_bridge(
    layers: List[WallLayer],
    area_m2: float,
    fluid_temp_c: float,
    ambient_air_temp_c: float,
    linear_bridge_length_m: float = 0.0,
    psi_w_mk: float = 0.25,  # Linear thermal transmittance across joints
    h_internal_w_m2k: float = 500.0,  # Water convective boundary
    h_external_w_m2k: float = 25.0,   # Exterior wind convective boundary
    relative_humidity_pct: float = 75.0
) -> ThermalBridgeAnalysisResult:
    """Calculates composite wall U-value, thermal bridge linear transmittance, and condensation risk."""
    r_layers = sum(layer.thermal_resistance for layer in layers)
    r_int = 1.0 / max(1.0, h_internal_w_m2k)
    r_ext = 1.0 / max(1.0, h_external_w_m2k)
    r_total = r_int + r_layers + r_ext
    u_composite = 1.0 / max(0.01, r_total)

    delta_t = fluid_temp_c - ambient_air_temp_c
    q_wall_w = u_composite * area_m2 * delta_t
    q_linear_w = psi_w_mk * linear_bridge_length_m * delta_t
    q_total_w = q_wall_w + q_linear_w

    # Uninsulated reference baseline (concrete only, e.g. 0.35m thick)
    r_unins = r_int + (0.35 / 1.80) + r_ext
    u_unins = 1.0 / r_unins
    q_unins_w = (u_unins * area_m2 + psi_w_mk * linear_bridge_length_m) * delta_t

    # Annual energy saved assuming 8760 h operation
    annual_saved_kwh = max(0.0, (q_unins_w - q_total_w) * 8760.0 / 1000.0)

    # Surface temperature calculations
    t_inner_surf = fluid_temp_c - (q_wall_w / (area_m2 * h_internal_w_m2k))
    t_outer_surf = ambient_air_temp_c + (q_wall_w / (area_m2 * h_external_w_m2k))

    dew_point = calculate_dew_point(ambient_air_temp_c, relative_humidity_pct)
    condensation = t_outer_surf <= dew_point

    hotspots = [
        {"location": "Expansion Joint Interstice", "concern": "Linear discontinuity without insulation break creates localized heat plume."},
        {"location": "Bridge Pier Abutment Contact", "concern": "High thermal mass pier acts as heat sink into ground bedrock."},
        {"location": "Conduit Support Saddles", "concern": "Steel cradle brackets conducting heat directly into concrete pedestals."}
    ]

    return ThermalBridgeAnalysisResult(
        composite_u_value_w_m2k=round(u_composite, 3),
        total_thermal_resistance_m2k_w=round(r_total, 3),
        uninsulated_heat_loss_kw=round(q_unins_w / 1000.0, 2),
        insulated_heat_loss_kw=round(q_total_w / 1000.0, 2),
        annual_energy_saved_kwh=round(annual_saved_kwh, 1),
        linear_bridge_heat_loss_kw=round(q_linear_w / 1000.0, 2),
        internal_surface_temp_c=round(t_inner_surf, 1),
        external_surface_temp_c=round(t_outer_surf, 1),
        condensation_risk=condensation,
        dew_point_temp_c=dew_point,
        hotspots=hotspots
    )
