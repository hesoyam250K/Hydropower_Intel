"""Analytics & Sensitivity workspace: parametric sweeps and multi-scenario comparisons."""

from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from src.database.storage import DatabaseManager
from src.analytics.performance import (
    sweep_flow_vs_power,
    sweep_head_vs_power,
    sweep_diameter_sensitivity,
    sweep_economic_tariff_sensitivity,
    build_scenario_comparison_table,
)


def render_analytics_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the Analytics & Sensitivity analysis section."""
    st.subheader("Analytics & Sensitivity Analysis")
    st.caption("Investigate hydraulic sensitivities, penstock diameter economics, tariff projections, and scenario comparisons.")

    # Defaults
    gross_head = float(active_project.get("gross_head_m", 30.0)) if active_project else 30.0
    design_flow = float(active_project.get("design_flow_lps", 1000.0)) if active_project else 1000.0
    pipe_d = float(active_project.get("pipe_diameter_m", 0.50)) if active_project else 0.50
    pipe_l = float(active_project.get("pipe_length_m", 150.0)) if active_project else 150.0
    roughness = float(active_project.get("roughness_mm", 0.045)) if active_project else 0.045

    subtab1, subtab2, subtab3, subtab4 = st.tabs([
        "Penstock Diameter Sizing",
        "Flow & Head Power Sweeps",
        "Economic Tariff Matrix",
        "Scenario Comparisons"
    ])

    # 1. Penstock Diameter Sensitivity
    with subtab1:
        st.markdown("##### Penstock Diameter Sensitivity (Hydraulic Friction vs Power Recovery)")
        st.caption("Demonstrates the steep non-linear power recovery as internal pipe diameter increases.")

        d_col1, d_col2 = st.columns([0.8, 1.2])
        with d_col1:
            sweep_flow_m3s = st.number_input("Design Flow (m³/s)", min_value=0.1, max_value=50.0, value=design_flow/1000.0, step=0.1)
            sweep_head = st.number_input("Gross Head (m)", min_value=1.0, max_value=1000.0, value=gross_head, step=1.0)
            sweep_len = st.number_input("Penstock Length (m)", min_value=10.0, max_value=10000.0, value=pipe_l, step=10.0)
            min_d = st.number_input("Min Diameter (m)", min_value=0.15, max_value=2.0, value=0.25, step=0.05)
            max_d = st.number_input("Max Diameter (m)", min_value=0.30, max_value=5.0, value=1.00, step=0.05)

        diam_df = sweep_diameter_sensitivity(
            flow_m3s=sweep_flow_m3s,
            gross_head_m=sweep_head,
            pipe_length_m=sweep_len,
            roughness_mm=roughness,
            min_diameter_m=min_d,
            max_diameter_m=max_d,
            steps=20
        )

        with d_col2:
            fig, ax1 = plt.subplots(figsize=(6.5, 3.8), facecolor="#1E293B")
            ax1.set_facecolor("#0F172A")

            # Left axis: Friction Loss
            ax1.plot(diam_df["diameter_mm"], diam_df["total_head_loss_m"], color="#EF4444", linewidth=2.0, label="Head Loss (m)")
            ax1.set_xlabel("Penstock Diameter (mm)", color="#94A3B8", fontsize=9)
            ax1.set_ylabel("Total Head Loss (m)", color="#EF4444", fontsize=9)
            ax1.tick_params(colors="#94A3B8", labelsize=8.5)
            for spine in ax1.spines.values():
                spine.set_color("#334155")
            ax1.grid(True, linestyle="--", alpha=0.2, color="#94A3B8")

            # Right axis: Power
            ax2 = ax1.twinx()
            ax2.plot(diam_df["diameter_mm"], diam_df["power_kw"], color="#10B981", linewidth=2.0, linestyle="--", label="Power Output (kW)")
            ax2.set_ylabel("Electrical Power (kW)", color="#10B981", fontsize=9)
            ax2.tick_params(colors="#10B981", labelsize=8.5)
            for spine in ax2.spines.values():
                spine.set_color("#334155")

            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        st.dataframe(diam_df[["diameter_mm", "velocity_mps", "friction_loss_m", "loss_ratio_pct", "power_kw", "annual_energy_mwh"]], use_container_width=True, hide_index=True)

    # 2. Flow & Head Sweeps
    with subtab2:
        st.markdown("##### Parametric Power Sweeps")
        sw1, sw2 = st.columns(2)

        with sw1:
            st.markdown("###### Flow Rate vs Generated Power")
            flow_sweep_df = sweep_flow_vs_power(
                gross_head_m=gross_head,
                pipe_diameter_m=pipe_d,
                pipe_length_m=pipe_l,
                min_flow_lps=200.0,
                max_flow_lps=max(2500.0, design_flow * 2.0),
                steps=20
            )

            fig_f, ax_f = plt.subplots(figsize=(5.5, 3.2), facecolor="#1E293B")
            ax_f.set_facecolor("#0F172A")
            ax_f.plot(flow_sweep_df["flow_lps"], flow_sweep_df["electrical_power_kw"], color="#38BDF8", linewidth=2.0)
            ax_f.set_xlabel("Flow Rate (L/s)", color="#94A3B8", fontsize=8.5)
            ax_f.set_ylabel("Power Output (kW)", color="#94A3B8", fontsize=8.5)
            ax_f.tick_params(colors="#94A3B8", labelsize=8)
            ax_f.grid(True, linestyle="--", alpha=0.2, color="#94A3B8")
            for spine in ax_f.spines.values():
                spine.set_color("#334155")
            fig_f.tight_layout()
            st.pyplot(fig_f)
            plt.close(fig_f)

        with sw2:
            st.markdown("###### Gross Head Elevation vs Power")
            head_sweep_df = sweep_head_vs_power(
                flow_lps=design_flow,
                min_head_m=5.0,
                max_head_m=max(100.0, gross_head * 2.5),
                steps=20
            )

            fig_h, ax_h = plt.subplots(figsize=(5.5, 3.2), facecolor="#1E293B")
            ax_h.set_facecolor("#0F172A")
            ax_h.plot(head_sweep_df["gross_head_m"], head_sweep_df["electrical_power_kw"], color="#F59E0B", linewidth=2.0)
            ax_h.set_xlabel("Gross Head (m)", color="#94A3B8", fontsize=8.5)
            ax_h.set_ylabel("Power Output (kW)", color="#94A3B8", fontsize=8.5)
            ax_h.tick_params(colors="#94A3B8", labelsize=8)
            ax_h.grid(True, linestyle="--", alpha=0.2, color="#94A3B8")
            for spine in ax_h.spines.values():
                spine.set_color("#334155")
            fig_h.tight_layout()
            st.pyplot(fig_h)
            plt.close(fig_h)

    # 3. Economic Tariff Matrix
    with subtab3:
        st.markdown("##### Annual Generation Revenue Sensitivity ($ / year)")
        st.caption("Projected gross electricity sales matrix across differing feed-in tariffs and plant capacity factors.")

        base_annual_mwh = (design_flow / 1000.0) * 9.81 * (gross_head - 1.5) * 0.82 * 8760.0 * 0.85 / 1000.0
        econ_df = sweep_economic_tariff_sensitivity(annual_energy_mwh=base_annual_mwh)
        st.dataframe(econ_df, use_container_width=True, hide_index=True)
        st.caption("CF = Capacity Factor (hours generating per year / 8,760 hours).")

    # 4. Scenario Comparisons
    with subtab4:
        st.markdown("##### Multi-Scenario Comparison")
        saved_calcs = db.list_calculations(project_id=active_project.get("id") if active_project else None)
        if not saved_calcs or len(saved_calcs) < 2:
            st.info("Save at least 2 calculation runs in the Power Calculator to perform a side-by-side design comparison.")
        else:
            calc_items = [c["results"] for c in saved_calcs]
            for i, c in enumerate(saved_calcs):
                calc_items[i]["name"] = c.get("name", f"Run {c['id']}")

            comp_df = build_scenario_comparison_table(calc_items)
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
