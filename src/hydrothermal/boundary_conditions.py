"""Boundary conditions and operational environments for hydrothermal analysis."""

from dataclasses import dataclass
from typing import Optional


SUPPORT_CONDITIONS = {
    "fully_restrained": ("Fully Restrained (Fixed both ends, R = 1.0)", 1.0),
    "semi_restrained": ("Semi-Restrained (Elastomeric bearings / flexible piers, R = 0.5)", 0.5),
    "free_expansion": ("Free Expansion (Sliding guided expansion joint, R = 0.0)", 0.0),
    "custom": ("Custom User Restraint Factor", None),
}


@dataclass
class HydrothermalBoundaryConditions:
    """Operational thermal and structural boundary conditions."""
    flow_lps: float = 1000.0                   # Hydraulic discharge
    inlet_temp_c: float = 12.0                  # Fluid inlet temperature (°C)
    outlet_temp_c: Optional[float] = None       # Fluid outlet temperature (°C) or auto-calculated
    ambient_air_temp_c: float = -5.0            # Ambient exterior temperature (°C) (e.g., winter freeze)
    ambient_river_temp_c: float = 8.0           # River / tailwater ambient temperature (°C)
    u_value_w_m2k: float = 4.5                  # Overall heat-transfer coefficient U (W/m²·K)
    bridge_length_m: float = 60.0               # Span / conduit length L₀ (m)
    heat_transfer_area_m2: float = 180.0        # Exposed perimeter × length (m²)
    wall_thickness_m: float = 0.35              # Conduit / pier wall thickness (m)
    support_condition: str = "semi_restrained"  # Support type
    restraint_factor: float = 0.5               # Structural restraint factor R in [0.0, 1.0]
    construction_datum_temp_c: float = 15.0     # Reference baseline stress-free temperature T_datum (°C)

    @property
    def flow_m3s(self) -> float:
        """Volumetric discharge in cubic metres per second."""
        return self.flow_lps / 1000.0
