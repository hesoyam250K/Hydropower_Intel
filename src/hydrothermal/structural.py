"""Thermal expansion and thermal stress calculations for bridge and conduit structures.

Implements:
1. Thermal expansion: ΔL = α * L0 * ΔT (metres and millimetres)
2. Idealized thermal stress: σ = R * E * α * ΔT (Megapascals)
3. Structural utilization ratio against yield strength.

Explicitly documents idealized 1D assumptions versus 3D finite-element analysis.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from src.hydrothermal.materials import EngineeringMaterial, get_material


@dataclass
class ThermalStructuralResult:
    """Quantitative results of thermal expansion and structural stress modeling."""
    initial_length_m: float
    expansion_m: float
    expansion_mm: float
    temperature_differential_c: float  # T_struct - T_datum
    restraint_factor: float            # R in [0.0, 1.0]
    thermal_stress_mpa: float          # σ (MPa)
    stress_nature: str                 # 'Compression' or 'Tension'
    allowable_strength_mpa: float      # Yield / characteristic strength
    utilization_ratio_pct: float       # (|σ| / σ_yield) * 100
    risk_level: str                    # 'LOW', 'MODERATE', 'ELEVATED', 'CRITICAL'
    engineering_qualification: str
    formula_substitutions: List[Dict[str, str]]


def calculate_thermal_expansion(
    initial_length_m: float,
    alpha_1_k: float,
    delta_t_c: float
) -> float:
    """Calculates linear thermal expansion:

    ΔL = α * L₀ * ΔT (metres)
    """
    return alpha_1_k * initial_length_m * delta_t_c


def calculate_thermal_stress(
    youngs_modulus_mpa: float,
    alpha_1_k: float,
    delta_t_c: float,
    restraint_factor: float = 1.0
) -> float:
    """Calculates induced thermal stress under structural restraint:

    σ = R * E * α * ΔT (MPa)

    Parameters:
    - youngs_modulus_mpa: Material elastic modulus E (MPa)
    - alpha_1_k: Thermal expansion coefficient α (1/K)
    - delta_t_c: Temperature change relative to construction datum ΔT (K or °C)
    - restraint_factor: Support boundary condition factor R (0.0 = free, 1.0 = fully fixed)
    """
    clamped_r = max(0.0, min(1.0, restraint_factor))
    return clamped_r * youngs_modulus_mpa * alpha_1_k * delta_t_c


def analyze_thermal_structural_behavior(
    initial_length_m: float,
    structure_temp_c: float,
    datum_temp_c: float = 15.0,
    restraint_factor: float = 0.5,
    material: Optional[EngineeringMaterial] = None
) -> ThermalStructuralResult:
    """Computes expansion, stress, and structural risk indicators."""
    mat = material or get_material("reinforced_concrete")
    delta_t = structure_temp_c - datum_temp_c

    delta_l_m = calculate_thermal_expansion(
        initial_length_m=initial_length_m,
        alpha_1_k=mat.thermal_expansion_coeff_1_k,
        delta_t_c=delta_t
    )
    delta_l_mm = delta_l_m * 1000.0

    sigma_mpa = calculate_thermal_stress(
        youngs_modulus_mpa=mat.youngs_modulus_mpa,
        alpha_1_k=mat.thermal_expansion_coeff_1_k,
        delta_t_c=delta_t,
        restraint_factor=restraint_factor
    )

    if delta_t > 0:
        stress_nature = "Thermal Compression (Structure is warmer than construction datum; expansion is restrained)"
    elif delta_t < 0:
        stress_nature = "Thermal Tension (Structure is colder than construction datum; contraction is restrained)"
    else:
        stress_nature = "Zero Thermal Stress (At baseline construction temperature)"

    utilization_pct = (abs(sigma_mpa) / max(1.0, mat.yield_strength_mpa)) * 100.0

    if utilization_pct > 70.0:
        risk_level = "CRITICAL (Exceeds 70% allowable design capacity; expansion joints or bearings required)"
    elif utilization_pct > 40.0:
        risk_level = "ELEVATED (Substantial thermal stress; check secondary cracking and joint rotation)"
    elif utilization_pct > 15.0:
        risk_level = "MODERATE (Standard engineering thermal movements accommodated by bearings)"
    else:
        risk_level = "LOW (Negligible thermal stress; within standard serviceability limit states)"

    qualification = (
        "IMPORTANT CIVIL/STRUCTURAL ENGINEERING QUALIFICATION: "
        "The calculated stress σ = R·E·α·ΔT is a simplified 1D unaxial estimate based on "
        f"restraint factor R = {restraint_factor:.2f}. In actual bridge and aqueduct engineering, "
        "stresses vary spatially across deck cross-sections due to non-linear temperature gradients, "
        "Poisson coupling (ν), creep relaxation, and soil-structure interaction. "
        "This calculation serves as a preliminary sizing screening and must not be used as a certified FEA design."
    )

    steps = [
        {
            "step": "1. Structure Thermal Differential",
            "formula": "ΔT = T_structure - T_datum",
            "substitution": f"{structure_temp_c:.2f}°C - {datum_temp_c:.2f}°C",
            "result": f"{delta_t:.2f} °C",
        },
        {
            "step": "2. Unrestrained Linear Thermal Expansion",
            "formula": "ΔL = α × L₀ × ΔT",
            "substitution": f"{mat.thermal_expansion_coeff_1_k:.2e} 1/K × {initial_length_m:.2f} m × {delta_t:.2f} K",
            "result": f"{delta_l_mm:+.2f} mm ({delta_l_m:+.5f} m)",
        },
        {
            "step": "3. Restrained Thermal Stress",
            "formula": "σ = R × E × α × ΔT",
            "substitution": f"{restraint_factor:.2f} × {mat.youngs_modulus_mpa:.1f} MPa × {mat.thermal_expansion_coeff_1_k:.2e} 1/K × {delta_t:.2f} K",
            "result": f"{sigma_mpa:+.2f} MPa",
        },
        {
            "step": "4. Material Strength Utilization",
            "formula": "η_util = (|σ| / σ_allowable) × 100%",
            "substitution": f"(|{sigma_mpa:.2f}| MPa / {mat.yield_strength_mpa:.1f} MPa) × 100",
            "result": f"{utilization_pct:.1f}% ({risk_level.split()[0]})",
        },
    ]

    return ThermalStructuralResult(
        initial_length_m=initial_length_m,
        expansion_m=delta_l_m,
        expansion_mm=delta_l_mm,
        temperature_differential_c=delta_t,
        restraint_factor=restraint_factor,
        thermal_stress_mpa=sigma_mpa,
        stress_nature=stress_nature,
        allowable_strength_mpa=mat.yield_strength_mpa,
        utilization_ratio_pct=utilization_pct,
        risk_level=risk_level,
        engineering_qualification=qualification,
        formula_substitutions=steps
    )
