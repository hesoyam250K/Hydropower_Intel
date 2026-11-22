"""Engineering Insights workspace: rule-based diagnostic interpretation."""

from typing import Any, Dict, List, Optional
import streamlit as st

from src.database.storage import DatabaseManager
from src.engine.hydropower import calculate_comprehensive_hydropower
from src.insights.interpretation import (
    EngineeringObservation,
    generate_calculation_insights,
    generate_simulation_insights,
)
from src.simulation.scenarios import run_dynamic_simulation, SimulationConfig


def render_insights_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders rule-based engineering insights and diagnostics."""
    st.subheader("Engineering Insights & Diagnostics Engine")
    st.caption("Automated rule-based diagnostic evaluation of hydraulic calculations and transient simulation performance.")

    # Base values
    gross_head = float(active_project.get("gross_head_m", 28.0)) if active_project else 28.0
    design_flow = float(active_project.get("design_flow_lps", 1100.0)) if active_project else 1100.0
    pipe_d = float(active_project.get("pipe_diameter_m", 0.45)) if active_project else 0.45
    pipe_l = float(active_project.get("pipe_length_m", 160.0)) if active_project else 160.0
    efficiency = float(active_project.get("efficiency", 0.82)) if active_project else 0.82

    # Calculate baseline
    calc = calculate_comprehensive_hydropower(
        flow_lps=design_flow,
        gross_head_m=gross_head,
        loss_method="darcy_weisbach",
        pipe_diameter_m=pipe_d,
        pipe_length_m=pipe_l,
        efficiency=efficiency,
    )
    calc_insights = generate_calculation_insights(calc)

    # Run quick simulated load rejection for transient insights
    sim_cfg = SimulationConfig(duration_s=25.0, scenario_type="load_rejection", event_time_s=5.0)
    sim_res = run_dynamic_simulation(config=sim_cfg)
    sim_insights = generate_simulation_insights(sim_res)

    all_insights = calc_insights + sim_insights

    # Filters
    col1, col2 = st.columns([1, 2])
    with col1:
        cat_filter = st.selectbox(
            "Filter by Category",
            options=["All Categories", "Hydraulics", "Turbine Selection", "Economics & Energy", "Transient Dynamics"]
        )

    filtered = [
        obs for obs in all_insights
        if cat_filter == "All Categories" or obs.category == cat_filter
    ]

    st.markdown("---")
    st.markdown(f"##### Identified Observations ({len(filtered)})")

    for obs in filtered:
        border_color = {
            "CRITICAL": "#DC2626",
            "WARNING": "#D97706",
            "OPTIMIZATION": "#2563EB",
            "INFO": "#059669"
        }.get(obs.level, "#475569")

        badge_class = {
            "CRITICAL": "badge-alarm",
            "WARNING": "badge-warning",
            "OPTIMIZATION": "badge-simulated",
            "INFO": "badge-normal"
        }.get(obs.level, "badge-physical")

        st.markdown(
            f"""
            <div style="background-color: #1E293B; border: 1px solid #334155; border-left: 4px solid {border_color}; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 0.95rem; font-weight: 700; color: #F8FAFC;">{obs.title}</span>
                    <div>
                        <span class="badge {badge_class}">{obs.level}</span>
                        <span style="font-size: 0.75rem; color: #94A3B8; margin-left: 8px;">[{obs.category}]</span>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: #CBD5E1; margin-bottom: 6px; line-height: 1.4;">
                    <b>Observation:</b> {obs.observation}
                </div>
                <div style="font-size: 0.85rem; color: #93C5FD; margin-bottom: 6px; line-height: 1.4;">
                    <b>Recommendation:</b> {obs.recommendation}
                </div>
                <div style="font-size: 0.75rem; color: #64748B; font-family: monospace;">
                    Governing Principle: {obs.governing_principle}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
