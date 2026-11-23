"""Engineering material database for coupled hydrothermal and structural calculations.

Defines mechanical and thermophysical properties for civil hydropower structures,
aqueducts, conduits, and bridge elements.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EngineeringMaterial:
    """Thermophysical and mechanical properties of a structural material."""
    name: str
    thermal_conductivity_w_mk: float  # k (W/m·K)
    youngs_modulus_gpa: float          # E (GPa)
    thermal_expansion_coeff_1_k: float  # alpha (1/K)
    density_kg_m3: float               # rho (kg/m³)
    specific_heat_j_kgk: float         # cp (J/kg·K)
    poissons_ratio: float              # nu (dimensionless)
    yield_strength_mpa: float          # sigma_y (MPa)
    description: str

    @property
    def youngs_modulus_mpa(self) -> float:
        """Young's modulus in Megapascals (MPa)."""
        return self.youngs_modulus_gpa * 1000.0

    @property
    def thermal_expansion_micro(self) -> float:
        """Thermal expansion coefficient in microstrain per Kelvin (μm/m·K)."""
        return self.thermal_expansion_coeff_1_k * 1e6


# Standard Engineering Materials Catalog
MATERIAL_DATABASE: Dict[str, EngineeringMaterial] = {
    "reinforced_concrete": EngineeringMaterial(
        name="Reinforced Concrete (C30/37)",
        thermal_conductivity_w_mk=1.80,
        youngs_modulus_gpa=33.0,
        thermal_expansion_coeff_1_k=1.0e-5,   # 10.0 μm/m·K
        density_kg_m3=2400.0,
        specific_heat_j_kgk=1000.0,
        poissons_ratio=0.20,
        yield_strength_mpa=30.0,              # Characteristic compressive cube strength
        description="Standard hydraulic reinforced concrete for dam bodies, piers, and conduit decks."
    ),
    "structural_steel": EngineeringMaterial(
        name="Structural Steel (S355 / ASTM A36)",
        thermal_conductivity_w_mk=50.0,
        youngs_modulus_gpa=210.0,
        thermal_expansion_coeff_1_k=1.2e-5,   # 12.0 μm/m·K
        density_kg_m3=7850.0,
        specific_heat_j_kgk=490.0,
        poissons_ratio=0.30,
        yield_strength_mpa=355.0,
        description="High-strength structural steel for penstock shells, bridge trusses, and gates."
    ),
    "stainless_steel_316": EngineeringMaterial(
        name="Stainless Steel (AISI 316L)",
        thermal_conductivity_w_mk=16.0,
        youngs_modulus_gpa=193.0,
        thermal_expansion_coeff_1_k=1.6e-5,   # 16.0 μm/m·K
        density_kg_m3=8000.0,
        specific_heat_j_kgk=500.0,
        poissons_ratio=0.28,
        yield_strength_mpa=290.0,
        description="Corrosion-resistant marine/hydro grade steel for submerged valves and nozzles."
    ),
    "structural_aluminum": EngineeringMaterial(
        name="Aluminum Alloy (6061-T6)",
        thermal_conductivity_w_mk=167.0,
        youngs_modulus_gpa=69.0,
        thermal_expansion_coeff_1_k=2.3e-5,   # 23.0 μm/m·K
        density_kg_m3=2700.0,
        specific_heat_j_kgk=896.0,
        poissons_ratio=0.33,
        yield_strength_mpa=276.0,
        description="Lightweight structural alloy for overhead inspection catwalks and canopy frames."
    ),
    "hdpe_polymer": EngineeringMaterial(
        name="High-Density Polyethylene (HDPE)",
        thermal_conductivity_w_mk=0.45,
        youngs_modulus_gpa=1.0,
        thermal_expansion_coeff_1_k=1.5e-4,   # 150.0 μm/m·K
        density_kg_m3=955.0,
        specific_heat_j_kgk=1900.0,
        poissons_ratio=0.42,
        yield_strength_mpa=25.0,
        description="Thermoplastic smooth conduit and penstock corrosion lining."
    ),
    "polyurethane_insulation": EngineeringMaterial(
        name="Rigid Polyurethane Foam (PUR Insulation)",
        thermal_conductivity_w_mk=0.026,
        youngs_modulus_gpa=0.015,
        thermal_expansion_coeff_1_k=5.0e-5,
        density_kg_m3=40.0,
        specific_heat_j_kgk=1500.0,
        poissons_ratio=0.30,
        yield_strength_mpa=0.20,
        description="High-performance thermal insulation barrier for exposed aqueducts."
    ),
}


def get_material(key: str) -> EngineeringMaterial:
    """Retrieves an engineering material by key, defaulting to reinforced concrete."""
    return MATERIAL_DATABASE.get(key, MATERIAL_DATABASE["reinforced_concrete"])


def list_materials() -> Dict[str, str]:
    """Returns mapping of keys to human-readable material names."""
    return {k: m.name for k, m in MATERIAL_DATABASE.items()}
