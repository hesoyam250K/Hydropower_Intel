"""Validation rules and physical boundaries for hydrothermal and structural inputs."""

from dataclasses import dataclass
from typing import List, Optional
from src.hydrothermal.materials import EngineeringMaterial
from src.hydrothermal.boundary_conditions import HydrothermalBoundaryConditions


class HydrothermalValidationError(ValueError):
    """Raised when hydrothermal or thermal-structural parameters violate physical laws."""
    pass


@dataclass
class HydrothermalValidationResult:
    """Encapsulates validation outcome, errors, and engineering warnings."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def validate_hydrothermal_inputs(
    bc: HydrothermalBoundaryConditions,
    mat: EngineeringMaterial
) -> HydrothermalValidationResult:
    """Validates boundary conditions and material parameters."""
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Flow Rate
    if bc.flow_lps < 0:
        errors.append(f"Flow rate cannot be negative: {bc.flow_lps} L/s.")
    elif bc.flow_lps == 0:
        warnings.append("Flow rate is 0 L/s; convective fluid transport is zero (stagnant water).")

    # 2. Geometric Bounds
    if bc.bridge_length_m <= 0:
        errors.append(f"Structure length must be strictly positive: {bc.bridge_length_m} m.")
    elif bc.bridge_length_m > 5000:
        warnings.append(f"Bridge length {bc.bridge_length_m} m is unusually long for a hydro conduit span.")

    if bc.heat_transfer_area_m2 <= 0:
        errors.append(f"Heat-transfer area must be strictly positive: {bc.heat_transfer_area_m2} m².")

    if bc.wall_thickness_m <= 0:
        errors.append(f"Wall thickness must be strictly positive: {bc.wall_thickness_m} m.")

    # 3. Temperatures
    if bc.inlet_temp_c < -5.0 or bc.inlet_temp_c > 85.0:
        warnings.append(f"Inlet water temperature {bc.inlet_temp_c}°C is outside typical liquid water ranges.")

    if bc.inlet_temp_c <= 0.0:
        warnings.append(f"Inlet temperature {bc.inlet_temp_c}°C poses severe frazil/anchor ice risk in water channels.")

    if bc.outlet_temp_c is not None:
        if bc.outlet_temp_c < -5.0 or bc.outlet_temp_c > 95.0:
            warnings.append(f"Outlet water temperature {bc.outlet_temp_c}°C is outside realistic bounds.")

    if bc.ambient_air_temp_c < -60.0 or bc.ambient_air_temp_c > 65.0:
        errors.append(f"Ambient air temperature {bc.ambient_air_temp_c}°C violates terrestrial climate extremes.")

    delta_t_env = abs(bc.inlet_temp_c - bc.ambient_air_temp_c)
    if delta_t_env > 40.0:
        warnings.append(
            f"Extreme fluid-to-ambient thermal differential ({delta_t_env:.1f}°C). "
            "High risk of thermal cracking in thick concrete sections due to internal restraint."
        )

    # 4. Heat Transfer & Material Properties
    if bc.u_value_w_m2k <= 0:
        errors.append(f"Overall heat-transfer coefficient U must be strictly positive: {bc.u_value_w_m2k} W/m²·K.")
    elif bc.u_value_w_m2k > 50.0:
        warnings.append(f"U-value of {bc.u_value_w_m2k} W/m²·K is unusually high (typical uninsulated conduit is 3-8 W/m²·K).")

    if mat.thermal_conductivity_w_mk <= 0:
        errors.append(f"Thermal conductivity must be positive: {mat.thermal_conductivity_w_mk} W/m·K.")

    if mat.youngs_modulus_gpa <= 0:
        errors.append(f"Young's modulus must be positive: {mat.youngs_modulus_gpa} GPa.")

    if mat.thermal_expansion_coeff_1_k < 0:
        errors.append(f"Thermal expansion coefficient cannot be negative: {mat.thermal_expansion_coeff_1_k}.")

    if not (0.0 <= bc.restraint_factor <= 1.0):
        errors.append(f"Restraint factor must be between 0.0 and 1.0: {bc.restraint_factor} provided.")

    return HydrothermalValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
