"""Turbine regime classification, specific speed, and performance characteristics.

Covers:
1. Turbine type selection based on net head, discharge, and specific speed.
2. Part-load efficiency modeling (Pelton, Francis, Kaplan, Crossflow, Propeller).
3. Thoma's cavitation parameter assessment.
4. Specific speed calculations (Metric Ns and European nq).
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TurbineSelection:
    """Engineering assessment of turbine suitability."""
    primary_recommendation: str
    secondary_options: List[str]
    regime_category: str  # High Head, Medium Head, Low Head / High Flow
    metric_specific_speed_ns: Optional[float]
    kinematic_specific_speed_nq: Optional[float]
    recommended_rpm: Optional[int]
    description: str
    advantages: List[str]
    considerations: List[str]
    cavitation_risk: str
    thoma_sigma_estimate: Optional[float] = None


@dataclass
class TurbineRegimeThresholds:
    """Configurable head and flow boundaries for turbine classification."""
    pelton_min_head_m: float = 50.0
    francis_min_head_m: float = 15.0
    francis_max_head_m: float = 400.0
    kaplan_max_head_m: float = 35.0
    crossflow_max_head_m: float = 100.0
    crossflow_min_head_m: float = 3.0


# Standard grid synchronous speeds for 50 Hz and 60 Hz grids
STANDARD_RPM_50HZ = [3000, 1500, 1000, 750, 600, 500, 428, 375, 300, 250, 200, 150, 100]
STANDARD_RPM_60HZ = [3600, 1800, 1200, 900, 720, 600, 514, 450, 360, 300, 240, 180, 120]


def calculate_specific_speed_ns(power_kw: float, net_head_m: float, rpm: float) -> float:
    """Calculates Metric Specific Speed:

    Ns = N * sqrt(P_kW) / (H_net ^ 1.25)

    Where:
    - N is runner rotational speed in revolutions per minute (RPM).
    - P_kW is turbine shaft power in kilowatts.
    - H_net is effective net head in metres.
    """
    if net_head_m <= 0 or power_kw <= 0 or rpm <= 0:
        return 0.0
    return (rpm * math.sqrt(power_kw)) / (net_head_m ** 1.25)


def calculate_kinematic_specific_speed_nq(flow_m3s: float, net_head_m: float, rpm: float) -> float:
    """Calculates European kinematic specific speed nq:

    nq = N * sqrt(Q_m3s) / (H_net ^ 0.75)
    """
    if net_head_m <= 0 or flow_m3s <= 0 or rpm <= 0:
        return 0.0
    return (rpm * math.sqrt(flow_m3s)) / (net_head_m ** 0.75)


def estimate_optimal_rpm(net_head_m: float, flow_m3s: float, grid_freq_hz: float = 50.0) -> int:
    """Estimates the most practical synchronous generator speed based on head and flow."""
    if net_head_m <= 0 or flow_m3s <= 0:
        return 1000

    speeds = STANDARD_RPM_50HZ if grid_freq_hz == 50.0 else STANDARD_RPM_60HZ

    # Target specific speed heuristic for medium-head Francis / Kaplan
    if net_head_m > 150.0:
        # High head Pelton: peripheral velocity factor phi ~ 0.46
        target_rpm = 1500 if net_head_m < 300 else 1000
    elif net_head_m > 30.0:
        # Medium head Francis: target nq around 40-70
        target_rpm = 750 if flow_m3s > 2.0 else 1000
    else:
        # Low head Kaplan: higher discharge, lower rpm to prevent excessive tip speed & cavitation
        target_rpm = 300 if flow_m3s > 5.0 else 500

    # Find closest standard synchronous speed
    closest_rpm = min(speeds, key=lambda s: abs(s - target_rpm))
    return closest_rpm


def classify_turbine_regime(
    net_head_m: float,
    flow_m3s: float,
    power_kw: float,
    thresholds: Optional[TurbineRegimeThresholds] = None,
    grid_freq_hz: float = 50.0
) -> TurbineSelection:
    """Classifies the optimal turbine regime using engineering criteria.

    Accounts for net head, discharge, specific speed, and hydraulic operating envelopes.
    Explains advantages, operational trade-offs, and cavitation boundaries.
    """
    if thresholds is None:
        thresholds = TurbineRegimeThresholds()

    if net_head_m <= 0 or flow_m3s <= 0:
        return TurbineSelection(
            primary_recommendation="Indeterminate (Zero Head or Flow)",
            secondary_options=[],
            regime_category="No Power Generation",
            metric_specific_speed_ns=0.0,
            kinematic_specific_speed_nq=0.0,
            recommended_rpm=None,
            description="Hydraulic conditions are insufficient for power generation.",
            advantages=[],
            considerations=["Provide non-zero head and flow."],
            cavitation_risk="None"
        )

    rpm = estimate_optimal_rpm(net_head_m, flow_m3s, grid_freq_hz)
    ns = calculate_specific_speed_ns(power_kw, net_head_m, rpm)
    nq = calculate_kinematic_specific_speed_nq(flow_m3s, net_head_m, rpm)

    # Classification logic based on head and specific speed envelopes
    if net_head_m >= thresholds.pelton_min_head_m:
        # High Head Domain: Pelton, Turgo
        regime = "High Head — Impulse Regime"
        if flow_m3s < 0.5 or net_head_m > 200.0 or ns < 60.0:
            primary = "Pelton Impulse Turbine"
            secondary = ["Turgo Impulse", "Multi-Jet Pelton"]
            desc = (
                f"Net head of {net_head_m:.1f} m and flow of {flow_m3s:.3f} m³/s place the site firmly in the "
                "impulse turbine operating zone. Atmospheric runner casing avoids high pressure containment "
                "and offers exceptional partial-load efficiency."
            )
            advantages = [
                "Exceptional part-load efficiency down to 20% flow via multi-needle modulation.",
                "Impulse runner operates at atmospheric pressure; zero draft tube cavitation risk.",
                "Easy maintenance and nozzle needle replacement without dewatering tailrace.",
                "Robust against sand and silt sediment abrasion compared to reaction seals."
            ]
            considerations = [
                "Requires generous vertical drop; low efficiency at heads below 30-40 m.",
                "Loss of head between runner centerline and tailwater surface.",
                "Multiple nozzles required for larger discharges."
            ]
            cav_risk = "Negligible (Runner operates in air at atmospheric pressure)"
        else:
            primary = "Francis Reaction Turbine"
            secondary = ["Multi-Jet Pelton", "Turgo Impulse"]
            desc = (
                f"With a head of {net_head_m:.1f} m and substantial flow ({flow_m3s:.2f} m³/s), a compact "
                "Francis reaction runner provides higher power density and direct generator coupling."
            )
            advantages = [
                "Compact physical plant footprint with higher rotational speed.",
                "Recovers suction head via sealed draft tube down to tailrace level.",
                "High peak efficiency (often > 92% at rated flow)."
            ]
            considerations = [
                "Steep efficiency falloff when operating below 50-60% rated flow.",
                "Requires careful setting elevation relative to tailwater to avoid blade cavitation."
            ]
            cav_risk = "Moderate — requires verified suction setting (submergence)."

    elif net_head_m >= thresholds.francis_min_head_m:
        # Medium Head Domain: Francis, Crossflow, Turgo
        regime = "Medium Head — Mixed Flow Regime"
        if flow_m3s < 0.2 and net_head_m < 80.0:
            primary = "Crossflow (Banki-Michell) Turbine"
            secondary = ["Francis Turbine", "Turgo Impulse"]
            desc = (
                f"For modest discharges ({flow_m3s*1000:.0f} L/s) at medium head ({net_head_m:.1f} m), "
                "the Banki-Michell crossflow turbine offers low manufacturing costs and simple self-cleaning runner design."
            )
            advantages = [
                "Flat efficiency curve maintained across seasonal flow fluctuations.",
                "Significantly lower manufacturing and maintenance costs for micro-hydro.",
                "Self-cleaning runner less prone to clogging from debris."
            ]
            considerations = [
                "Lower peak efficiency (~80-84%) compared to optimized Francis runners.",
                "Atmospheric casing incurs small suction head loss."
            ]
            cav_risk = "Low"
        else:
            primary = "Francis Reaction Turbine"
            secondary = ["Propeller / Kaplan (if head < 25 m)", "Crossflow"]
            desc = (
                f"At {net_head_m:.1f} m net head and {flow_m3s:.2f} m³/s flow, a Francis reaction turbine is "
                "the worldwide engineering standard. Water enters radially through guide vanes and exits axially."
            )
            advantages = [
                "Industry benchmark peak hydraulic efficiency (90% to 94%).",
                "Wide commercial availability from international turbine manufacturers.",
                "Draft tube recovers velocity head, maximizing total energy yield."
            ]
            considerations = [
                "Poor performance and vortex rope vibrations below 40% rated discharge.",
                "Substantial civil engineering works needed for spiral casing and draft tube."
            ]
            cav_risk = "Moderate to High — Thoma's cavitation parameter sigma must be checked."

    else:
        # Low Head Domain: Kaplan, Propeller, Tubular/Bulb
        regime = "Low Head / High Flow — Axial Flow Regime"
        primary = "Kaplan (Double-Regulated Axial) Turbine"
        secondary = ["Propeller (Fixed Blade)", "Bulb / Tubular Turbine", "Very Low Head (VLH)"]
        desc = (
            f"Low net head of {net_head_m:.1f} m requires large volumetric throughput ({flow_m3s:.2f} m³/s). "
            "Axial-flow Kaplan turbines feature adjustable runner blades and guide vanes for high efficiency."
        )
        advantages = [
            "Maintains high efficiency over wide variations in both head and flow.",
            "High specific speed allows direct coupling to generators without high-ratio gearboxes.",
            "Minimal submergence requirements compared to large radial turbines."
        ]
        considerations = [
            "Complex blade pitch regulating mechanisms require regular oil/seal maintenance.",
            "Higher capital expenditure per installed kilowatt compared to high-head equipment."
        ]
        cav_risk = "High — Blade tip speeds and suction head require strict submergence analysis."

    # Empirical Thoma cavitation coefficient estimate for reaction turbines
    thoma_sigma = None
    if "Francis" in primary or "Kaplan" in primary:
        if nq > 0:
            thoma_sigma = round(0.043 * ((nq / 100.0) ** 1.33), 3)

    return TurbineSelection(
        primary_recommendation=primary,
        secondary_options=secondary,
        regime_category=regime,
        metric_specific_speed_ns=round(ns, 1),
        kinematic_specific_speed_nq=round(nq, 1),
        recommended_rpm=rpm,
        description=desc,
        advantages=advantages,
        considerations=considerations,
        cavitation_risk=cav_risk,
        thoma_sigma_estimate=thoma_sigma
    )


def calculate_part_load_efficiency(
    turbine_type: str,
    flow_fraction: float,
    peak_efficiency: float = 0.90
) -> float:
    """Calculates realistic part-load water-to-wire efficiency as a function of relative discharge (q = Q / Q_rated).

    - Pelton: Flat curve; holds efficiency well down to 0.20 Q_rated.
    - Francis: Sharp peak near 0.90 - 1.00 Q_rated; drops significantly below 0.50 Q_rated.
    - Kaplan: Very flat curve due to double regulation of runner blades + wicket gates.
    - Crossflow: Moderate peak, flat curve across broad range.
    """
    q = max(0.0, min(1.25, flow_fraction))
    if q < 0.10:
        return 0.0

    t_type = turbine_type.lower()
    if "pelton" in t_type or "turgo" in t_type or "impulse" in t_type:
        # Pelton model: holds ~85-92% from 0.25 to 1.10
        eff = peak_efficiency * (1.0 - 0.18 * ((1.0 - q) ** 2))
    elif "francis" in t_type:
        # Francis model: drops noticeably at partial loads
        if q >= 1.0:
            eff = peak_efficiency * (1.0 - 0.25 * ((q - 1.0) ** 2))
        else:
            eff = peak_efficiency * (1.0 - 0.65 * ((1.0 - q) ** 2) - 0.35 * ((1.0 - q) ** 4))
    elif "kaplan" in t_type or "bulb" in t_type:
        # Kaplan double-regulated: very broad flat curve
        eff = peak_efficiency * (1.0 - 0.15 * ((abs(1.0 - q)) ** 1.8))
    elif "crossflow" in t_type or "banki" in t_type:
        # Crossflow: flat curve, lower peak (~0.82)
        eff = min(peak_efficiency, 0.84) * (1.0 - 0.22 * ((1.0 - q) ** 2))
    else:
        # Generic turbine default
        eff = peak_efficiency * (1.0 - 0.35 * ((1.0 - q) ** 2))

    return max(0.0, min(peak_efficiency, eff))
