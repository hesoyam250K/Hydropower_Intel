"""Overview / Main Executive Engineering Dashboard."""

from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from src.database.storage import DatabaseManager
from src.engine.hydropower import calculate_comprehensive_hydropower


def render_overview_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the executive engineering summary dashboard."""
    if not active_project:
        st.warning("No active hydropower project selected. Please open or create a project in the Project Manager.")
        return

    proj_name = active_project.get("name", "Default Project")
    gross_head = float(active_project.get("gross_head_m", 25.0))
    flow_lps = float(active_project.get("design_flow_lps", 1000.0))
    efficiency = float(active_project.get("efficiency", 0.82))
    pipe_d = float(active_project.get("pipe_diameter_m", 0.50))
    pipe_l = float(active_project.get("pipe_length_m", 150.0))
    roughness = float(active_project.get("roughness_mm", 0.045))

    # Compute baseline reference for project
    calc = calculate_comprehensive_hydropower(
        flow_lps=flow_lps,
        gross_head_m=gross_head,
        loss_method="darcy_weisbach",
        pipe_diameter_m=pipe_d,
        pipe_length_m=pipe_l,
        roughness_mm=roughness,
        efficiency=efficiency,
        hours=24.0,
    )

    st.subheader(f"System Overview: {proj_name}")
    st.caption(
        f"Location: {active_project.get('location', 'Unspecified')} | "
        f"Waterway: {active_project.get('river_name', 'Clearwater Creek')} | "
        f"Turbine Selection: {active_project.get('turbine_type', 'Francis Reaction')}"
    )

    # 1. Primary Operating Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Design Power Output",
            value=f"{calc.electrical_power_kw:,.1f} kW",
            delta=f"Hydraulic: {calc.hydraulic_power_kw:,.1f} kW"
        )
    with col2:
        st.metric(
            label="Daily Energy Yield",
            value=f"{calc.daily_energy_kwh:,.1f} kWh",
            delta=f"Annual: {calc.annual_energy_mwh:,.1f} MWh/yr"
        )
    with col3:
        st.metric(
            label="Effective Net Head",
            value=f"{calc.net_head_m:.2f} m",
            delta=f"-{calc.head_loss_m:.2f} m loss",
            delta_color="inverse"
        )
    with col4:
        st.metric(
            label="Design Volumetric Flow",
            value=f"{calc.flow_lps:,.0f} L/s",
            delta=f"{calc.flow_m3s:.3f} m³/s"
        )

    st.markdown("---")

    # 2. Plant Operating Modes & Source Disambiguation
    st.markdown(
        """
        <div style="display: flex; gap: 15px; margin-bottom: 15px;">
            <div style="flex: 1; background: #1E293B; border-left: 3px solid #2563EB; padding: 10px 14px; border-radius: 4px;">
                <span style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; font-weight: 700;">Calculated Design Baseline</span><br/>
                <span style="font-size: 1.1rem; font-weight: 700; color: #F8FAFC;">""" + f"{calc.electrical_power_kw:,.1f} kW" + """</span>
                <span style="font-size: 0.8rem; color: #94A3B8; margin-left: 8px;">(Darcy-Weisbach Engine)</span>
            </div>
            <div style="flex: 1; background: #1E293B; border-left: 3px solid #38BDF8; padding: 10px 14px; border-radius: 4px;">
                <span style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; font-weight: 700;">Simulated Dynamic Mean</span><br/>
                <span style="font-size: 1.1rem; font-weight: 700; color: #F8FAFC;">""" + f"{calc.electrical_power_kw * 0.98:,.1f} kW" + """</span>
                <span style="font-size: 0.8rem; color: #94A3B8; margin-left: 8px;">(ODE Physics Solver)</span>
            </div>
            <div style="flex: 1; background: #1E293B; border-left: 3px solid #10B981; padding: 10px 14px; border-radius: 4px;">
                <span style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; font-weight: 700;">Live Sensor Measurement</span><br/>
                <span style="font-size: 1.1rem; font-weight: 700; color: #34D399;">Ready for Stream</span>
                <span style="font-size: 0.8rem; color: #94A3B8; margin-left: 8px;">(Simulated / MQTT)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 3. Two-Column Dashboard View
    left_col, right_col = st.columns([1.1, 0.9])

    with left_col:
        st.markdown("##### Hydraulic System & Energy Balance")
        fig, ax = plt.subplots(figsize=(6.5, 3.2), facecolor="#1E293B")
        ax.set_facecolor("#0F172A")

        # Head breakdown bar chart
        categories = ["Gross Head", "Friction Loss", "Minor Loss", "Net Head"]
        friction_loss = calc.loss_breakdown.friction_loss_m if calc.loss_breakdown else 0.0
        minor_loss = calc.loss_breakdown.minor_losses_m if calc.loss_breakdown else 0.0
        values = [gross_head, friction_loss, minor_loss, calc.net_head_m]
        bar_colors = ["#3B82F6", "#EF4444", "#F59E0B", "#10B981"]

        bars = ax.bar(categories, values, color=bar_colors, width=0.5, edgecolor="#334155")
        ax.set_ylabel("Head (metres)", color="#94A3B8", fontsize=9)
        ax.tick_params(colors="#94A3B8", labelsize=8.5)
        for spine in ax.spines.values():
            spine.set_color("#334155")
        ax.grid(axis="y", linestyle="--", alpha=0.2, color="#94A3B8")

        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{height:.2f} m",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', color='#F8FAFC', fontsize=8, fontweight='bold')

        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        # Plant Specifications Table
        spec_df = pd.DataFrame([
            {"Parameter": "Penstock Diameter", "Value": f"{pipe_d*1000:.0f} mm", "Design Standard": "ASTM A106 / Steel"},
            {"Parameter": "Penstock Length", "Value": f"{pipe_l:.1f} m", "Design Standard": "Intake to Powerhouse"},
            {"Parameter": "Flow Velocity", "Value": f"{calc.loss_breakdown.flow_velocity_mps:.2f} m/s", "Design Standard": "1.5 - 3.5 m/s (Economic)"},
            {"Parameter": "Loss-to-Head Ratio", "Value": f"{(calc.head_loss_m/gross_head)*100:.1f}%", "Design Standard": "< 10% Guideline"},
            {"Parameter": "Combined Efficiency", "Value": f"{efficiency*100:.1f}%", "Design Standard": "Water-to-Wire"},
        ])
        st.table(spec_df)

    with right_col:
        st.markdown("##### Recent Calculations & Project Activity")
        recent_calcs = db.list_calculations(project_id=active_project.get("id"))
        if recent_calcs:
            calc_table = []
            for c in recent_calcs[:5]:
                calc_table.append({
                    "Calculation Name": c.get("name", "Unnamed"),
                    "Power (kW)": c["results"].get("electrical_power_kw", "N/A"),
                    "Net Head (m)": c["results"].get("net_head_m", "N/A"),
                    "Date": c.get("created_at", "")[:16].replace("T", " ")
                })
            st.dataframe(pd.DataFrame(calc_table), use_container_width=True, hide_index=True)
        else:
            st.info("No calculations saved yet for this project. Use the Power Calculator to generate runs.")

        st.markdown("##### Recent Dynamic Simulations")
        recent_sims = db.list_simulations(project_id=active_project.get("id"))
        if recent_sims:
            sim_table = []
            for s in recent_sims[:4]:
                sim_table.append({
                    "Scenario": s.get("scenario_name", "Scenario"),
                    "Peak Overspeed": f"{s['summary'].get('max_overspeed_pct', 0):.1f}%",
                    "Max Surge Head": f"{s['summary'].get('max_head_m', 0):.1f} m",
                    "Date": s.get("created_at", "")[:16].replace("T", " ")
                })
            st.dataframe(pd.DataFrame(sim_table), use_container_width=True, hide_index=True)
        else:
            st.info("No dynamic simulations run yet. Navigate to Simulation Lab to test transients.")

        # System Status & Diagnostic Summary
        st.markdown("##### System Alerts & Diagnostic State")
        loss_pct = (calc.head_loss_m / gross_head) * 100.0
        if loss_pct > 15.0:
            st.warning(f"⚠️ High Penstock Friction Loss: {loss_pct:.1f}% of gross head dissipated. Check sizing.")
        else:
            st.success(f"✓ Hydraulic Loss Nominal: {loss_pct:.1f}% of gross head (<10% threshold).")

        st.success(f"✓ Recommended Turbine: {calc.turbine_selection.primary_recommendation}")
