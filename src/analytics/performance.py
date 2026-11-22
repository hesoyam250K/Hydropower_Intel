"""Engineering sensitivity analysis, parametric sweeps, and scenario comparison."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.engine.hydropower import (
    calculate_comprehensive_hydropower,
    HydropowerCalculationResult,
    WATER_DENSITY,
    G_STANDARD,
)
from src.engine.head_loss import calculate_darcy_weisbach_loss


def sweep_flow_vs_power(
    gross_head_m: float = 25.0,
    pipe_diameter_m: float = 0.50,
    pipe_length_m: float = 150.0,
    roughness_mm: float = 0.045,
    efficiency: float = 0.82,
    min_flow_lps: float = 100.0,
    max_flow_lps: float = 2000.0,
    steps: int = 25
) -> pd.DataFrame:
    """Computes power output, friction loss, and net head across a range of flow rates."""
    flows_lps = np.linspace(min_flow_lps, max_flow_lps, steps)
    records = []

    for q_lps in flows_lps:
        q_m3s = q_lps / 1000.0
        loss = calculate_darcy_weisbach_loss(
            flow_m3s=q_m3s,
            gross_head_m=gross_head_m,
            pipe_diameter_m=pipe_diameter_m,
            pipe_length_m=pipe_length_m,
            roughness_mm=roughness_mm
        )
        net_head = max(0.0, gross_head_m - loss.total_head_loss_m)
        hyd_kw = (WATER_DENSITY * G_STANDARD * q_m3s * net_head) / 1000.0
        elec_kw = hyd_kw * efficiency

        records.append({
            "flow_lps": round(q_lps, 1),
            "flow_m3s": round(q_m3s, 4),
            "velocity_mps": round(loss.flow_velocity_mps, 2),
            "head_loss_m": round(loss.total_head_loss_m, 3),
            "net_head_m": round(net_head, 2),
            "hydraulic_power_kw": round(hyd_kw, 2),
            "electrical_power_kw": round(elec_kw, 2),
        })

    return pd.DataFrame(records)


def sweep_head_vs_power(
    flow_lps: float = 1000.0,
    min_head_m: float = 5.0,
    max_head_m: float = 100.0,
    head_loss_m: float = 1.5,
    efficiency: float = 0.82,
    steps: int = 25
) -> pd.DataFrame:
    """Computes power output across varying gross head elevations."""
    heads = np.linspace(min_head_m, max_head_m, steps)
    q_m3s = flow_lps / 1000.0
    records = []

    for h_gross in heads:
        net_head = max(0.0, h_gross - head_loss_m)
        elec_kw = (WATER_DENSITY * G_STANDARD * q_m3s * net_head * efficiency) / 1000.0
        records.append({
            "gross_head_m": round(h_gross, 1),
            "head_loss_m": round(head_loss_m, 2),
            "net_head_m": round(net_head, 2),
            "electrical_power_kw": round(elec_kw, 2),
            "daily_energy_kwh": round(elec_kw * 24.0, 1),
        })

    return pd.DataFrame(records)


def sweep_diameter_sensitivity(
    flow_m3s: float = 1.0,
    gross_head_m: float = 30.0,
    pipe_length_m: float = 200.0,
    roughness_mm: float = 0.045,
    efficiency: float = 0.82,
    min_diameter_m: float = 0.25,
    max_diameter_m: float = 1.00,
    steps: int = 20
) -> pd.DataFrame:
    """Investigates penstock diameter sensitivity: velocity, head loss, and power generation."""
    diameters = np.linspace(min_diameter_m, max_diameter_m, steps)
    records = []

    for d in diameters:
        loss = calculate_darcy_weisbach_loss(
            flow_m3s=flow_m3s,
            gross_head_m=gross_head_m,
            pipe_diameter_m=d,
            pipe_length_m=pipe_length_m,
            roughness_mm=roughness_mm
        )
        net_head = max(0.0, gross_head_m - loss.total_head_loss_m)
        elec_kw = (WATER_DENSITY * G_STANDARD * flow_m3s * net_head * efficiency) / 1000.0
        annual_mwh = (elec_kw * 8760.0 * 0.85) / 1000.0

        records.append({
            "diameter_mm": round(d * 1000.0, 0),
            "diameter_m": round(d, 3),
            "velocity_mps": round(loss.flow_velocity_mps, 2),
            "reynolds": round(loss.reynolds_number, 0),
            "friction_loss_m": round(loss.friction_loss_m, 3),
            "total_head_loss_m": round(loss.total_head_loss_m, 3),
            "loss_ratio_pct": round((loss.total_head_loss_m / gross_head_m) * 100.0, 1),
            "net_head_m": round(net_head, 2),
            "power_kw": round(elec_kw, 2),
            "annual_energy_mwh": round(annual_mwh, 1),
        })

    return pd.DataFrame(records)


def sweep_economic_tariff_sensitivity(
    annual_energy_mwh: float,
    tariffs: Optional[List[float]] = None,
    capacity_factors: Optional[List[float]] = None
) -> pd.DataFrame:
    """Generates revenue matrix for varying feed-in tariffs ($/kWh) and capacity factors."""
    tariff_list = tariffs or [0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
    cf_list = capacity_factors or [0.60, 0.70, 0.80, 0.85, 0.90]

    # Normalize baseline to 100% capacity factor
    base_mwh_100 = annual_energy_mwh / 0.85 if annual_energy_mwh > 0 else 1000.0

    rows = []
    for tariff in tariff_list:
        row = {"tariff_usd_kwh": tariff}
        for cf in cf_list:
            gen_mwh = base_mwh_100 * cf
            rev_usd = gen_mwh * 1000.0 * tariff
            row[f"CF_{int(cf*100)}%"] = round(rev_usd, 0)
        rows.append(row)

    return pd.DataFrame(rows)


def build_scenario_comparison_table(scenarios: List[Dict[str, Any]]) -> pd.DataFrame:
    """Constructs a clean comparison table for multiple saved scenarios or designs."""
    if not scenarios:
        return pd.DataFrame()

    formatted = []
    for s in scenarios:
        formatted.append({
            "Scenario / Record": s.get("name", "Unnamed"),
            "Flow (L/s)": s.get("flow_lps", 0.0),
            "Gross Head (m)": s.get("gross_head_m", 0.0),
            "Head Loss (m)": s.get("head_loss_m", 0.0),
            "Net Head (m)": s.get("net_head_m", 0.0),
            "Efficiency (%)": round(s.get("efficiency", 0.8) * 100.0, 1),
            "Power (kW)": s.get("power_kw", s.get("electrical_power_kw", 0.0)),
            "Daily Energy (kWh)": s.get("daily_energy_kwh", 0.0),
            "Annual Energy (MWh)": s.get("annual_energy_mwh", 0.0),
            "Turbine Type": s.get("turbine_recommended", "N/A"),
        })

    return pd.DataFrame(formatted)
