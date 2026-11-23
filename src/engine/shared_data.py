"""Shared engineering data architecture for HydroPower Intelligence.

Ensures tight coupling between:
1. Hydraulic Calculator Engine
2. Dynamic Physics & Governor Simulation
3. Live SCADA Telemetry
4. Hydrothermal Bridge Analysis
5. Interactive 3D Engineering & Hologram Renderers

Guarantees single source of truth across all modules without duplicated calculations.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.engine.hydropower import HydropowerCalculationResult
from src.hydrothermal.heat_transfer import HydrothermalHeatTransferResult
from src.hydrothermal.structural import ThermalStructuralResult


@dataclass
class SharedEngineeringContext:
    """Unified data packet passed between calculations, simulations, hydrothermal analysis, and 3D viewers."""
    project_id: Optional[int] = None
    project_name: str = "Hydropower Project"
    scenario_name: str = "Design Steady State"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data_provenance: str = "CALCULATED_DESIGN"  # 'CALCULATED_DESIGN', 'SIMULATION_DYNAMIC', 'LIVE_SCADA_SIMULATED', 'LIVE_SCADA_MQTT'

    # 1. Hydraulic Parameters
    flow_lps: float = 1000.0
    flow_m3s: float = 1.0
    gross_head_m: float = 25.0
    head_loss_m: float = 1.5
    net_head_m: float = 23.5
    water_velocity_mps: float = 2.5
    water_density_kg_m3: float = 1000.0

    # 2. Electromechanical Parameters
    water_to_wire_efficiency: float = 0.82
    hydraulic_power_kw: float = 230.5
    electrical_power_kw: float = 189.0
    runner_speed_rpm: float = 1000.0
    frequency_hz: float = 50.0
    gate_position_pct: float = 80.0
    simulation_time_s: Optional[float] = None

    # 3. Hydrothermal & Thermal-Bridge Parameters
    water_inlet_temp_c: float = 12.0
    water_outlet_temp_c: float = 11.8
    ambient_air_temp_c: float = -5.0
    fluid_thermal_transfer_kw: float = 836.8
    thermal_bridge_loss_kw: float = 12.2
    thermal_expansion_mm: float = 2.5
    thermal_stress_mpa: float = 3.2
    structural_restraint_factor: float = 0.5
    active_material_name: str = "Reinforced Concrete (C30/37)"

    # 4. 3D Model & Component Inspection Metadata
    active_model_mode: str = "BOTH"  # 'HYDROPOWER_ONLY', 'BRIDGE_ONLY', 'BOTH'
    visualization_mode: str = "FLOW"  # 'FLOW', 'THERMAL', 'STRUCTURAL'
    active_component_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes context for JSON transfer to Three.js or database."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedEngineeringContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def build_shared_context_from_calc(
    calc: HydropowerCalculationResult,
    project: Optional[Dict[str, Any]] = None,
    thermal_res: Optional[HydrothermalHeatTransferResult] = None,
    struct_res: Optional[ThermalStructuralResult] = None,
) -> SharedEngineeringContext:
    """Builds a shared context directly from hydraulic calculator and hydrothermal outputs."""
    p_name = project.get("name", "Hydropower Scheme") if project else "Hydropower Scheme"
    p_id = project.get("id") if project else None

    vel = calc.loss_breakdown.flow_velocity_mps if calc.loss_breakdown else 2.5
    rpm = calc.turbine_selection.recommended_rpm if calc.turbine_selection and calc.turbine_selection.recommended_rpm else 1000.0

    inlet_t = thermal_res.inlet_temp_c if thermal_res else 12.0
    outlet_t = thermal_res.outlet_temp_c if thermal_res else 11.8
    amb_t = thermal_res.ambient_air_temp_c if thermal_res else -5.0
    th_kw = thermal_res.fluid_thermal_transfer_kw if thermal_res else 0.0
    br_kw = thermal_res.thermal_bridge_loss_kw if thermal_res else 0.0

    exp_mm = struct_res.expansion_mm if struct_res else 0.0
    stress_mpa = struct_res.thermal_stress_mpa if struct_res else 0.0
    r_factor = struct_res.restraint_factor if struct_res else 0.5

    return SharedEngineeringContext(
        project_id=p_id,
        project_name=p_name,
        scenario_name="Design Baseline",
        data_provenance="CALCULATED_DESIGN",
        flow_lps=calc.flow_lps,
        flow_m3s=calc.flow_m3s,
        gross_head_m=calc.gross_head_m,
        head_loss_m=calc.head_loss_m,
        net_head_m=calc.net_head_m,
        water_velocity_mps=vel,
        water_density_kg_m3=calc.water_density_kg_m3,
        water_to_wire_efficiency=calc.efficiency,
        hydraulic_power_kw=calc.hydraulic_power_kw,
        electrical_power_kw=calc.electrical_power_kw,
        runner_speed_rpm=rpm,
        frequency_hz=50.0,
        gate_position_pct=80.0,
        water_inlet_temp_c=inlet_t,
        water_outlet_temp_c=outlet_t,
        ambient_air_temp_c=amb_t,
        fluid_thermal_transfer_kw=th_kw,
        thermal_bridge_loss_kw=br_kw,
        thermal_expansion_mm=exp_mm,
        thermal_stress_mpa=stress_mpa,
        structural_restraint_factor=r_factor,
    )
