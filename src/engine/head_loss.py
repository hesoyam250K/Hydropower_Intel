"""Hydraulic head loss calculation engine.

Implements:
1. Darcy-Weisbach friction equation with Colebrook-White, Swamee-Jain, and Churchill formulations.
2. Minor losses from pipe fittings, valves, bends, and entrances.
3. Hazen-Williams empirical equation (metric).
4. Standard penstock materials roughness database.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from scipy.optimize import root_scalar


# Standard physical constants
G_STANDARD = 9.81  # Acceleration due to gravity (m/s^2)
WATER_DENSITY = 1000.0  # kg/m^3 for freshwater
KINEMATIC_VISCOSITY_20C = 1.004e-6  # m^2/s at 20°C


@dataclass
class PipeMaterial:
    """Engineering material specifications for penstock friction analysis."""
    name: str
    roughness_mm: float  # Equivalent sand roughness epsilon (mm)
    hazen_williams_c: float  # Empirical C roughness coefficient
    description: str


# Engineering pipe material standard catalog
PIPE_MATERIALS: Dict[str, PipeMaterial] = {
    "smooth_pe_pvc": PipeMaterial(
        name="PVC / HDPE (High-Density Polyethylene)",
        roughness_mm=0.0015,
        hazen_williams_c=150.0,
        description="Extremely smooth plastic pipe, modern micro-hydro standard."
    ),
    "welded_steel_new": PipeMaterial(
        name="Welded Steel (New / Smooth coated)",
        roughness_mm=0.045,
        hazen_williams_c=140.0,
        description="High-pressure penstocks with epoxy or bitumen internal lining."
    ),
    "commercial_steel": PipeMaterial(
        name="Commercial Carbon Steel (Standard)",
        roughness_mm=0.060,
        hazen_williams_c=130.0,
        description="Standard commercial schedule steel penstocks."
    ),
    "ductile_iron": PipeMaterial(
        name="Ductile Iron (Cement-mortar lined)",
        roughness_mm=0.250,
        hazen_williams_c=130.0,
        description="Heavy-duty municipal and medium-head hydro installations."
    ),
    "concrete_smooth": PipeMaterial(
        name="Concrete (Smooth / Precast pipes)",
        roughness_mm=0.360,
        hazen_williams_c=120.0,
        description="Tunnels, low-pressure penstocks, and canal siphons."
    ),
    "riveted_steel_aged": PipeMaterial(
        name="Riveted / Aged Steel",
        roughness_mm=0.500,
        hazen_williams_c=110.0,
        description="Historical or aged penstocks exhibiting moderate tuberculation."
    ),
    "cast_iron_aged": PipeMaterial(
        name="Cast Iron (Old / Moderate corrosion)",
        roughness_mm=1.000,
        hazen_williams_c=100.0,
        description="Older infrastructure subject to incrustation."
    ),
}


# Standard Minor Loss Coefficients (K-values: h_m = K * v^2 / 2g)
FITTING_K_VALUES: Dict[str, Tuple[str, float]] = {
    "entrance_bellmouth": ("Intake: Bellmouth / Rounded entrance (r/D > 0.15)", 0.05),
    "entrance_flush": ("Intake: Square / Flush sharp-edged entrance", 0.50),
    "entrance_projecting": ("Intake: Inward projecting (Borda mouthpiece)", 0.80),
    "bend_90_long_radius": ("Elbow: 90° Long radius bend (R/D >= 1.5)", 0.20),
    "bend_90_standard": ("Elbow: 90° Standard radius bend", 0.35),
    "bend_45_standard": ("Elbow: 45° Standard bend", 0.18),
    "bend_22_5": ("Elbow: 22.5° Gradual deflection", 0.10),
    "valve_gate_open": ("Valve: Gate valve (100% fully open)", 0.15),
    "valve_butterfly_open": ("Valve: Butterfly valve (100% open)", 0.30),
    "valve_globe_open": ("Valve: Globe valve (100% open)", 4.00),
    "valve_check_swing": ("Valve: Swing check / non-return valve", 2.00),
    "contraction_sudden": ("Transition: Sudden pipe contraction", 0.35),
    "expansion_sudden": ("Transition: Sudden pipe expansion", 0.80),
    "exit_submerged": ("Discharge: Submerged exit to tailrace (K = 1.0)", 1.00),
}


@dataclass
class HeadLossBreakdown:
    """Detailed engineering breakdown of hydraulic head losses."""
    method: str
    flow_m3s: float
    flow_velocity_mps: float
    pipe_diameter_m: float
    pipe_length_m: float
    velocity_head_m: float  # v^2 / 2g
    reynolds_number: float
    flow_regime: str  # Laminar, Critical/Transition, Turbulent
    friction_factor: float
    friction_loss_m: float
    minor_losses_m: float
    total_head_loss_m: float
    roughness_mm: Optional[float] = None
    hazen_williams_c: Optional[float] = None
    minor_loss_items: List[Dict[str, float]] = field(default_factory=list)
    formula_substituted: str = ""
    notes: List[str] = field(default_factory=list)


def calculate_flow_velocity(flow_m3s: float, diameter_m: float) -> Tuple[float, float]:
    """Calculates cross-sectional area (m^2) and mean flow velocity (m/s)."""
    if diameter_m <= 0:
        raise ValueError(f"Pipe diameter must be positive: {diameter_m} m")
    area = math.pi * (diameter_m ** 2) / 4.0
    if flow_m3s <= 0:
        return area, 0.0
    velocity = flow_m3s / area
    return area, velocity


def calculate_reynolds_number(
    velocity_mps: float,
    diameter_m: float,
    kinematic_viscosity: float = KINEMATIC_VISCOSITY_20C
) -> float:
    """Calculates dimensionless Reynolds number: Re = (v * D) / nu."""
    if kinematic_viscosity <= 0:
        raise ValueError("Kinematic viscosity must be strictly positive.")
    return (velocity_mps * diameter_m) / kinematic_viscosity


def solve_darcy_friction_factor(
    reynolds: float,
    relative_roughness: float,
    method: str = "colebrook"
) -> float:
    """Calculates Darcy-Weisbach friction factor f across all flow regimes.

    - Laminar (Re <= 2000): Hagen-Poiseuille law: f = 64 / Re.
    - Transition (2000 < Re < 4000): Churchill continuous formulation.
    - Turbulent (Re >= 4000):
        Implicit Colebrook-White equation solved via Brent's method,
        with Swamee-Jain explicit equation as initial seed and fallback.
    """
    if reynolds <= 0:
        return 0.0

    # Laminar flow
    if reynolds <= 2000.0:
        return 64.0 / reynolds

    # Swamee-Jain approximation (explicit)
    term1 = relative_roughness / 3.7
    term2 = 5.74 / (reynolds ** 0.9)
    log_arg = term1 + term2
    f_swamee = 0.25 / (math.log10(max(log_arg, 1e-12)) ** 2)

    if method == "swamee_jain":
        return f_swamee

    # Transition zone (2000 < Re < 4000): Churchill (1977) formula
    if 2000.0 < reynolds < 4000.0:
        a_term = (2.457 * math.log(1.0 / ((7.0 / reynolds) ** 0.9 + 0.27 * relative_roughness))) ** 16
        b_term = (37530.0 / reynolds) ** 16
        f_churchill = 8.0 * ((8.0 / reynolds) ** 12 + 1.0 / ((a_term + b_term) ** 1.5)) ** (1.0 / 12.0)
        return f_churchill

    # Fully turbulent (Re >= 4000): Colebrook-White implicit solution
    def colebrook_func(f_val: float) -> float:
        inv_sqrt_f = 1.0 / math.sqrt(f_val)
        inner = (relative_roughness / 3.7) + (2.51 / (reynolds * math.sqrt(f_val)))
        return inv_sqrt_f + 2.0 * math.log10(max(inner, 1e-15))

    try:
        sol = root_scalar(
            colebrook_func,
            bracket=[0.005, 0.15],
            method="brentq",
            x0=f_swamee
        )
        if sol.converged and sol.root > 0:
            return float(sol.root)
    except Exception:
        pass

    return f_swamee


def calculate_darcy_weisbach_loss(
    flow_m3s: float,
    gross_head_m: float,
    pipe_diameter_m: float,
    pipe_length_m: float,
    roughness_mm: float,
    minor_fittings: Optional[List[Tuple[str, int]]] = None,
    g: float = G_STANDARD,
    kinematic_viscosity: float = KINEMATIC_VISCOSITY_20C
) -> HeadLossBreakdown:
    """Calculates pipe head loss using the rigorous Darcy-Weisbach formulation.

    hf = f * (L / D) * (v^2 / 2g)
    hm = sum(K) * (v^2 / 2g)
    """
    area, velocity = calculate_flow_velocity(flow_m3s, pipe_diameter_m)
    v_head = (velocity ** 2) / (2.0 * g) if velocity > 0 else 0.0

    if flow_m3s <= 0 or velocity == 0.0:
        return HeadLossBreakdown(
            method="Darcy-Weisbach",
            flow_m3s=0.0,
            flow_velocity_mps=0.0,
            pipe_diameter_m=pipe_diameter_m,
            pipe_length_m=pipe_length_m,
            velocity_head_m=0.0,
            reynolds_number=0.0,
            flow_regime="Zero Flow",
            friction_factor=0.0,
            friction_loss_m=0.0,
            minor_losses_m=0.0,
            total_head_loss_m=0.0,
            roughness_mm=roughness_mm,
            formula_substituted="v = 0 m/s -> hf = 0.0 m",
            notes=["No flow running through penstock."]
        )

    reynolds = calculate_reynolds_number(velocity, pipe_diameter_m, kinematic_viscosity)
    relative_roughness = (roughness_mm / 1000.0) / pipe_diameter_m

    if reynolds <= 2000.0:
        regime = "Laminar (Re <= 2000)"
    elif reynolds < 4000.0:
        regime = "Critical / Transition (2000 < Re < 4000)"
    else:
        regime = "Turbulent (Re >= 4000)"

    f = solve_darcy_friction_factor(reynolds, relative_roughness)
    hf = f * (pipe_length_m / pipe_diameter_m) * v_head

    # Minor losses summation
    minor_items: List[Dict[str, float]] = []
    total_k = 0.0
    if minor_fittings:
        for fitting_key, count in minor_fittings:
            if count <= 0:
                continue
            if fitting_key in FITTING_K_VALUES:
                name, k_val = FITTING_K_VALUES[fitting_key]
                k_subtotal = k_val * count
                total_k += k_subtotal
                minor_items.append({
                    "name": name,
                    "k_single": k_val,
                    "count": float(count),
                    "k_total": k_subtotal,
                    "loss_m": k_subtotal * v_head
                })

    hm = total_k * v_head
    total_loss = hf + hm

    notes: List[str] = []
    if velocity < 1.0:
        notes.append(f"Mean velocity ({velocity:.2f} m/s) is below economic penstock guidelines (1.5-3.5 m/s); check for silt deposition risk.")
    elif velocity > 4.0:
        notes.append(f"Mean velocity ({velocity:.2f} m/s) is high (> 4 m/s); excessive water hammer surge risk and dynamic abrasion.")

    loss_ratio = (total_loss / gross_head_m * 100.0) if gross_head_m > 0 else 0.0
    if loss_ratio > 10.0:
        notes.append(f"Penstock loss represents {loss_ratio:.1f}% of gross head (> 10% design threshold). Consider a larger penstock diameter.")

    formula_str = (
        f"v = {velocity:.3f} m/s, Re = {reynolds:,.0f} ({regime})\n"
        f"f = {f:.4f}, (L/D) = {pipe_length_m/pipe_diameter_m:.1f}, v²/2g = {v_head:.4f} m\n"
        f"hf = {f:.4f} × ({pipe_length_m:.1f} / {pipe_diameter_m:.3f}) × {v_head:.4f} = {hf:.3f} m\n"
        f"hm = ΣK × v²/2g = {total_k:.2f} × {v_head:.4f} = {hm:.3f} m\n"
        f"Hloss = hf + hm = {total_loss:.3f} m"
    )

    return HeadLossBreakdown(
        method="Darcy-Weisbach",
        flow_m3s=flow_m3s,
        flow_velocity_mps=velocity,
        pipe_diameter_m=pipe_diameter_m,
        pipe_length_m=pipe_length_m,
        velocity_head_m=v_head,
        reynolds_number=reynolds,
        flow_regime=regime,
        friction_factor=f,
        friction_loss_m=hf,
        minor_losses_m=hm,
        total_head_loss_m=total_loss,
        roughness_mm=roughness_mm,
        minor_loss_items=minor_items,
        formula_substituted=formula_str,
        notes=notes
    )


def calculate_hazen_williams_loss(
    flow_m3s: float,
    gross_head_m: float,
    pipe_diameter_m: float,
    pipe_length_m: float,
    c_factor: float,
    minor_fittings: Optional[List[Tuple[str, int]]] = None,
    g: float = G_STANDARD
) -> HeadLossBreakdown:
    """Calculates pipe head loss using the metric Hazen-Williams empirical formula:

    hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)

    Applicability and limitations:
    - Strictly valid for fresh water at normal ambient temperatures (~15°C to 25°C).
    - Valid for turbulent flow in circular pipes with diameter D >= 0.05 m (50 mm).
    - Ignores kinematic viscosity and temperature variations.
    """
    area, velocity = calculate_flow_velocity(flow_m3s, pipe_diameter_m)
    v_head = (velocity ** 2) / (2.0 * g) if velocity > 0 else 0.0

    if flow_m3s <= 0 or velocity == 0.0:
        return HeadLossBreakdown(
            method="Hazen-Williams",
            flow_m3s=0.0,
            flow_velocity_mps=0.0,
            pipe_diameter_m=pipe_diameter_m,
            pipe_length_m=pipe_length_m,
            velocity_head_m=0.0,
            reynolds_number=0.0,
            flow_regime="Zero Flow",
            friction_factor=0.0,
            friction_loss_m=0.0,
            minor_losses_m=0.0,
            total_head_loss_m=0.0,
            hazen_williams_c=c_factor,
            formula_substituted="v = 0 m/s -> hf = 0.0 m",
            notes=["No flow running through penstock."]
        )

    # Hazen-Williams metric friction loss
    hf = 10.67 * pipe_length_m * (flow_m3s ** 1.852) / ((c_factor ** 1.852) * (pipe_diameter_m ** 4.870))

    # Minor losses summation
    minor_items: List[Dict[str, float]] = []
    total_k = 0.0
    if minor_fittings:
        for fitting_key, count in minor_fittings:
            if count <= 0:
                continue
            if fitting_key in FITTING_K_VALUES:
                name, k_val = FITTING_K_VALUES[fitting_key]
                k_subtotal = k_val * count
                total_k += k_subtotal
                minor_items.append({
                    "name": name,
                    "k_single": k_val,
                    "count": float(count),
                    "k_total": k_subtotal,
                    "loss_m": k_subtotal * v_head
                })

    hm = total_k * v_head
    total_loss = hf + hm

    reynolds = calculate_reynolds_number(velocity, pipe_diameter_m)
    regime = "Turbulent (Hazen-Williams assumption)"

    notes: List[str] = [
        "Hazen-Williams is an empirical formulation valid for water at ~20°C and turbulent pipe flow.",
        "Note: Unlike Darcy-Weisbach, Hazen-Williams does not explicitly account for water viscosity."
    ]

    loss_ratio = (total_loss / gross_head_m * 100.0) if gross_head_m > 0 else 0.0
    if loss_ratio > 10.0:
        notes.append(f"Penstock loss represents {loss_ratio:.1f}% of gross head (> 10% design threshold).")

    formula_str = (
        f"hf = 10.67 × L × Q^1.852 / (C^1.852 × D^4.870)\n"
        f"hf = 10.67 × {pipe_length_m:.1f} × ({flow_m3s:.4f})^1.852 / (({c_factor:.1f})^1.852 × ({pipe_diameter_m:.3f})^4.870) = {hf:.3f} m\n"
        f"hm = ΣK × v²/2g = {total_k:.2f} × {v_head:.4f} = {hm:.3f} m\n"
        f"Hloss = hf + hm = {total_loss:.3f} m"
    )

    return HeadLossBreakdown(
        method="Hazen-Williams",
        flow_m3s=flow_m3s,
        flow_velocity_mps=velocity,
        pipe_diameter_m=pipe_diameter_m,
        pipe_length_m=pipe_length_m,
        velocity_head_m=v_head,
        reynolds_number=reynolds,
        flow_regime=regime,
        friction_factor=0.0,
        friction_loss_m=hf,
        minor_losses_m=hm,
        total_head_loss_m=total_loss,
        hazen_williams_c=c_factor,
        minor_loss_items=minor_items,
        formula_substituted=formula_str,
        notes=notes
    )
