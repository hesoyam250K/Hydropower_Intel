"""Core hydropower engineering calculation engine.

Implements the fundamental hydraulic-to-electric power equations:
    P = rho * g * Q * H_net * eta
    P(kW) = (rho * g * Q * H_net * eta) / 1000
    H_net = H_gross - H_loss
    E(kWh) = P(kW) * hours

Maintains full numerical precision internally and formats for presentation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.engine.validation import validate_hydropower_inputs, HydraulicValidationError
from src.engine.head_loss import (
    HeadLossBreakdown,
    calculate_darcy_weisbach_loss,
    calculate_hazen_williams_loss,
    G_STANDARD,
    WATER_DENSITY,
)
from src.engine.turbine import (
    TurbineSelection,
    classify_turbine_regime,
    TurbineRegimeThresholds,
)


@dataclass
class HydropowerCalculationResult:
    """Complete, transparent engineering calculation result."""
    flow_lps: float
    flow_m3s: float
    gross_head_m: float
    head_loss_m: float
    net_head_m: float
    efficiency: float
    operating_hours: float
    capacity_factor: float
    water_density_kg_m3: float
    gravity_m_s2: float

    # Calculated Power & Energy outputs
    hydraulic_power_kw: float
    electrical_power_kw: float
    energy_kwh: float
    daily_energy_kwh: float
    annual_energy_mwh: float

    # Associated engineering details
    loss_breakdown: Optional[HeadLossBreakdown] = None
    turbine_selection: Optional[TurbineSelection] = None
    warnings: List[str] = field(default_factory=list)
    substitution_steps: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to a dictionary suitable for storage or serialization."""
        return {
            "flow_lps": self.flow_lps,
            "flow_m3s": self.flow_m3s,
            "gross_head_m": self.gross_head_m,
            "head_loss_m": self.head_loss_m,
            "net_head_m": self.net_head_m,
            "efficiency": self.efficiency,
            "operating_hours": self.operating_hours,
            "capacity_factor": self.capacity_factor,
            "hydraulic_power_kw": round(self.hydraulic_power_kw, 3),
            "electrical_power_kw": round(self.electrical_power_kw, 3),
            "energy_kwh": round(self.energy_kwh, 2),
            "daily_energy_kwh": round(self.daily_energy_kwh, 2),
            "annual_energy_mwh": round(self.annual_energy_mwh, 3),
            "turbine_recommended": (
                self.turbine_selection.primary_recommendation
                if self.turbine_selection else "N/A"
            ),
            "loss_method": (
                self.loss_breakdown.method
                if self.loss_breakdown else "Manual Input"
            ),
        }


def flow_lps_to_m3s(flow_lps: float) -> float:
    """Converts volumetric flow from Litres/second to cubic metres/second:

    Q (m^3/s) = Q (L/s) / 1000.0
    """
    if flow_lps < 0:
        raise HydraulicValidationError(f"Flow rate cannot be negative: {flow_lps} L/s")
    return flow_lps / 1000.0


def flow_m3s_to_lps(flow_m3s: float) -> float:
    """Converts volumetric flow from cubic metres/second to Litres/second:

    Q (L/s) = Q (m^3/s) * 1000.0
    """
    if flow_m3s < 0:
        raise HydraulicValidationError(f"Flow rate cannot be negative: {flow_m3s} m^3/s")
    return flow_m3s * 1000.0


def calculate_hydropower(
    flow_lps: float,
    gross_head_m: float,
    head_loss_m: float = 0.0,
    efficiency: float = 0.75,
    hours: float = 24.0,
    density: float = WATER_DENSITY,
    gravity: float = G_STANDARD,
    capacity_factor: float = 1.0,
) -> Dict[str, float]:
    """Reference modular calculation function.

    Validates inputs, computes net head, instantaneous power (kW), and cumulative energy (kWh).
    Used directly in unit verification tests.
    """
    if flow_lps < 0 or gross_head_m < 0 or not (0.0 <= efficiency <= 1.0) or hours < 0:
        raise ValueError("Invalid hydraulic parameters.")

    if head_loss_m < 0:
        raise ValueError("Head loss cannot be negative.")

    q_m3s = flow_lps / 1000.0
    net_head = max(0.0, gross_head_m - head_loss_m)

    # Fundamental formula: P = rho * g * Q * H_net * eta
    power_kw = (density * gravity * q_m3s * net_head * efficiency) / 1000.0
    energy_kwh = power_kw * hours

    return {
        "flow_lps": flow_lps,
        "flow_m3s": q_m3s,
        "gross_head_m": gross_head_m,
        "head_loss_m": head_loss_m,
        "net_head_m": round(net_head, 2),
        "power_kw": round(power_kw, 3),
        "energy_kwh": round(energy_kwh, 2),
    }


def calculate_comprehensive_hydropower(
    flow_lps: Optional[float] = None,
    flow_m3s: Optional[float] = None,
    gross_head_m: float = 20.0,
    loss_method: str = "manual",  # 'manual', 'darcy_weisbach', 'hazen_williams'
    manual_head_loss_m: float = 0.0,
    pipe_diameter_m: Optional[float] = None,
    pipe_length_m: Optional[float] = None,
    roughness_mm: float = 0.045,
    c_factor: float = 130.0,
    minor_fittings: Optional[List[Tuple[str, int]]] = None,
    efficiency: float = 0.75,
    hours: float = 24.0,
    capacity_factor: float = 0.85,
    density: float = WATER_DENSITY,
    gravity: float = G_STANDARD,
    turbine_thresholds: Optional[TurbineRegimeThresholds] = None,
    grid_freq_hz: float = 50.0,
) -> HydropowerCalculationResult:
    """Full-featured hydropower calculation workspace engine.

    Handles flow conversion, friction loss calculation (Darcy-Weisbach / Hazen-Williams / Manual),
    net head calculation, electrical power, energy yields, turbine regime classification,
    and step-by-step formula substitutions.
    """
    # 1. Flow normalization
    if flow_m3s is not None:
        q_m3s = float(flow_m3s)
        q_lps = flow_m3s_to_lps(q_m3s)
    elif flow_lps is not None:
        q_lps = float(flow_lps)
        q_m3s = flow_lps_to_m3s(q_lps)
    else:
        q_lps = 1000.0
        q_m3s = 1.0

    # 2. Validation
    val = validate_hydropower_inputs(
        flow_lps=q_lps,
        gross_head_m=gross_head_m,
        efficiency=efficiency,
        hours=hours,
        pipe_diameter_m=pipe_diameter_m,
        pipe_length_m=pipe_length_m,
        roughness_mm=roughness_mm if loss_method == "darcy_weisbach" else None,
        c_factor=c_factor if loss_method == "hazen_williams" else None,
    )
    if not val.is_valid:
        raise HydraulicValidationError("; ".join(val.errors))

    # 3. Head loss calculation
    loss_breakdown: Optional[HeadLossBreakdown] = None
    if loss_method == "darcy_weisbach":
        if pipe_diameter_m is None or pipe_length_m is None:
            raise HydraulicValidationError("Darcy-Weisbach method requires internal pipe diameter and length.")
        loss_breakdown = calculate_darcy_weisbach_loss(
            flow_m3s=q_m3s,
            gross_head_m=gross_head_m,
            pipe_diameter_m=pipe_diameter_m,
            pipe_length_m=pipe_length_m,
            roughness_mm=roughness_mm,
            minor_fittings=minor_fittings,
            g=gravity,
        )
        head_loss = loss_breakdown.total_head_loss_m
    elif loss_method == "hazen_williams":
        if pipe_diameter_m is None or pipe_length_m is None:
            raise HydraulicValidationError("Hazen-Williams method requires internal pipe diameter and length.")
        loss_breakdown = calculate_hazen_williams_loss(
            flow_m3s=q_m3s,
            gross_head_m=gross_head_m,
            pipe_diameter_m=pipe_diameter_m,
            pipe_length_m=pipe_length_m,
            c_factor=c_factor,
            minor_fittings=minor_fittings,
            g=gravity,
        )
        head_loss = loss_breakdown.total_head_loss_m
    else:
        # Manual head loss input
        head_loss = max(0.0, float(manual_head_loss_m))

    net_head = max(0.0, gross_head_m - head_loss)

    # 4. Power & Energy Calculations
    hydraulic_power_kw = (density * gravity * q_m3s * net_head) / 1000.0
    electrical_power_kw = hydraulic_power_kw * efficiency
    energy_kwh = electrical_power_kw * hours
    daily_energy_kwh = electrical_power_kw * 24.0
    # Annual energy in MWh = (P_kW * 8760 hours * Capacity Factor) / 1000
    annual_energy_mwh = (electrical_power_kw * 8760.0 * capacity_factor) / 1000.0

    # 5. Turbine selection
    turbine_sel = classify_turbine_regime(
        net_head_m=net_head,
        flow_m3s=q_m3s,
        power_kw=electrical_power_kw,
        thresholds=turbine_thresholds,
        grid_freq_hz=grid_freq_hz,
    )

    # 6. Step-by-Step Substitution
    steps: List[Dict[str, str]] = [
        {
            "step": "1. Volumetric Flow Rate Conversion",
            "formula": "Q (m³/s) = Q (L/s) / 1,000",
            "substitution": f"{q_lps:,.2f} L/s ÷ 1,000 = {q_m3s:.4f} m³/s",
            "result": f"{q_m3s:.4f} m³/s",
        },
        {
            "step": "2. Net Hydraulic Head Determination",
            "formula": "H_net = H_gross - H_loss",
            "substitution": f"{gross_head_m:.2f} m - {head_loss:.3f} m = {net_head:.3f} m",
            "result": f"{net_head:.3f} m",
        },
        {
            "step": "3. Theoretical Hydraulic Power (100% Efficiency)",
            "formula": "P_hyd (kW) = (ρ × g × Q × H_net) / 1,000",
            "substitution": f"({density:.1f} × {gravity:.2f} × {q_m3s:.4f} × {net_head:.3f}) / 1,000",
            "result": f"{hydraulic_power_kw:.3f} kW",
        },
        {
            "step": "4. Generated Electrical Power Output",
            "formula": "P_elec (kW) = P_hyd × η",
            "substitution": f"{hydraulic_power_kw:.3f} kW × {efficiency:.4f}",
            "result": f"{electrical_power_kw:.3f} kW",
        },
        {
            "step": "5. Electrical Energy Production",
            "formula": "E (kWh) = P_elec (kW) × Operating Duration (h)",
            "substitution": f"{electrical_power_kw:.3f} kW × {hours:.1f} h",
            "result": f"{energy_kwh:,.2f} kWh",
        },
        {
            "step": "6. Annual Generation Forecast",
            "formula": "E_annual (MWh) = (P_elec × 8,760 h × Capacity Factor) / 1,000",
            "substitution": f"({electrical_power_kw:.3f} kW × 8,760 h × {capacity_factor:.2f}) / 1,000",
            "result": f"{annual_energy_mwh:,.2f} MWh/yr",
        },
    ]

    return HydropowerCalculationResult(
        flow_lps=q_lps,
        flow_m3s=q_m3s,
        gross_head_m=gross_head_m,
        head_loss_m=head_loss,
        net_head_m=net_head,
        efficiency=efficiency,
        operating_hours=hours,
        capacity_factor=capacity_factor,
        water_density_kg_m3=density,
        gravity_m_s2=gravity,
        hydraulic_power_kw=hydraulic_power_kw,
        electrical_power_kw=electrical_power_kw,
        energy_kwh=energy_kwh,
        daily_energy_kwh=daily_energy_kwh,
        annual_energy_mwh=annual_energy_mwh,
        loss_breakdown=loss_breakdown,
        turbine_selection=turbine_sel,
        warnings=val.warnings,
        substitution_steps=steps,
    )
