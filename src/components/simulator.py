"""Simulation Lab interface for interactive dynamic hydraulic and electromechanical modeling."""

from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.database.storage import DatabaseManager
from src.simulation.scenarios import (
    run_dynamic_simulation,
    SimulationConfig,
    SimulationResults,
)
from src.simulation.hydraulic_model import HydraulicPlantParams
from src.simulation.turbine_model import TurbineGeneratorParams
from src.simulation.control_system import GovernorParams
from src.analytics.reports import export_simulation_to_csv


def render_simulator_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the dynamic simulation laboratory workspace."""
    st.subheader("Simulation Lab: Dynamic Hydraulic & Governor Transients")
    st.caption("Investigate penstock water column inertia, runner rotational dynamics, grid load events, and governor control.")

    # Base parameters from project
    base_head = float(active_project.get("gross_head_m", 30.0)) if active_project else 30.0
    base_flow = float(active_project.get("design_flow_lps", 1200.0)) / 1000.0 if active_project else 1.20
    base_pipe_d = float(active_project.get("pipe_diameter_m", 0.50)) if active_project else 0.50
    base_pipe_l = float(active_project.get("pipe_length_m", 150.0)) if active_project else 150.0

    # Controls expander
    with st.expander("Simulation Parameters & Operating Scenarios", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("###### 1. Operating Scenario")
            scenario_choice = st.selectbox(
                "Transient Scenario",
                options=[
                    "steady_state",
                    "load_rejection",
                    "load_acceptance",
                    "reservoir_drawdown",
                    "rapid_gate_closure"
                ],
                format_func=lambda s: {
                    "steady_state": "Steady-State Baseline",
                    "load_rejection": "Sudden Load Rejection (Grid Trip)",
                    "load_acceptance": "Load Acceptance (+50% Step Increase)",
                    "reservoir_drawdown": "Reservoir Drawdown / Drought Inflow",
                    "rapid_gate_closure": "Rapid Emergency Gate Closure (Surge)",
                }[s],
                index=1,
                help="Select the operational event or disturbance to simulate."
            )

            sim_duration = st.slider("Simulation Duration (seconds)", min_value=10.0, max_value=120.0, value=45.0, step=5.0)
            event_time = st.slider("Event Start Time (seconds)", min_value=2.0, max_value=sim_duration - 5.0, value=10.0, step=1.0)
            init_gate_pct = st.slider("Initial Gate Opening (%)", min_value=20.0, max_value=100.0, value=80.0, step=5.0)

        with col2:
            st.markdown("###### 2. Hydraulic Plant Dimensions")
            water_level = st.number_input("Reservoir Surface Level (m)", min_value=5.0, max_value=500.0, value=base_head, step=1.0)
            rated_flow = st.number_input("Rated Turbine Flow (m³/s)", min_value=0.1, max_value=20.0, value=base_flow, step=0.1)
            pipe_l = st.number_input("Penstock Length L (m)", min_value=10.0, max_value=5000.0, value=base_pipe_l, step=10.0)
            pipe_d = st.number_input("Penstock Diameter D (m)", min_value=0.1, max_value=5.0, value=base_pipe_d, step=0.05)
            res_area = st.number_input("Reservoir Surface Area (m²)", min_value=500.0, max_value=1000000.0, value=15000.0, step=1000.0)

        with col3:
            st.markdown("###### 3. Turbine, Generator & Governor")
            rated_rpm = st.selectbox("Synchronous Speed (RPM)", options=[1500, 1000, 750, 600, 500, 375], index=1)
            base_load_kw = st.number_input("Nominal Electrical Load (kW)", min_value=10.0, max_value=5000.0, value=220.0, step=10.0)
            inertia_j = st.number_input("Rotating Inertia J (kg·m²)", min_value=50.0, max_value=2000.0, value=250.0, step=25.0)
            gov_auto = st.checkbox("Automatic Governor Active (PID)", value=True)

    # Configure objects
    plant_params = HydraulicPlantParams(
        reservoir_area_m2=res_area,
        initial_water_level_m=water_level,
        pipe_length_m=pipe_l,
        pipe_diameter_m=pipe_d,
        rated_flow_m3s=rated_flow
    )
    turb_params = TurbineGeneratorParams(
        rated_speed_rpm=float(rated_rpm),
        moment_of_inertia_kg_m2=inertia_j
    )
    sim_config = SimulationConfig(
        duration_s=sim_duration,
        dt=0.05,
        scenario_type=scenario_choice,
        event_time_s=event_time,
        initial_gate=init_gate_pct / 100.0,
        nominal_electrical_load_kw=base_load_kw,
        governor_auto=gov_auto
    )

    # Execute simulation
    sim_res: SimulationResults = run_dynamic_simulation(
        plant_params=plant_params,
        turbine_params=turb_params,
        config=sim_config
    )

    # Display Summary Metrics
    st.markdown("#### Dynamic Transient Performance Indicators")
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        st.metric(
            "Peak Runner Speed",
            f"{sim_res.peak_speed_rpm:.0f} RPM",
            delta=f"+{sim_res.max_overspeed_pct:.1f}% Overspeed" if sim_res.max_overspeed_pct > 0 else "Nominal",
            delta_color="inverse" if sim_res.max_overspeed_pct > 20 else "normal"
        )
    with s2:
        st.metric(
            "Peak Transient Head",
            f"{sim_res.max_head_m:.1f} m",
            delta=f"+{sim_res.max_head_surge_pct:.1f}% Water Hammer Surge",
            delta_color="inverse" if sim_res.max_head_surge_pct > 15 else "normal"
        )
    with s3:
        st.metric(
            "Settling Time (±2%)",
            f"{sim_res.settling_time_s:.1f} s" if sim_res.settling_time_s else "N/A",
            delta="Governor Recovery"
        )
    with s4:
        st.metric(
            "Initial Power",
            f"{sim_res.initial_power_kw:.1f} kW",
            delta=f"Final: {sim_res.final_power_kw:.1f} kW"
        )
    with s5:
        st.metric(
            "Energy Generated",
            f"{sim_res.total_energy_kwh:.3f} kWh",
            delta=f"{sim_duration:.0f}s run"
        )

    # Engineering Graphs (4-Panel Matplotlib Multiplot)
    st.markdown("---")
    st.markdown("##### Transient Response Curves")

    fig, axes = plt.subplots(2, 2, figsize=(11, 6.5), facecolor="#1E293B")
    t = sim_res.time_s

    # Styling helper
    def style_ax(ax, title, ylabel):
        ax.set_facecolor("#0F172A")
        ax.set_title(title, color="#E2E8F0", fontsize=10, fontweight="bold", pad=8)
        ax.set_xlabel("Time (seconds)", color="#94A3B8", fontsize=8.5)
        ax.set_ylabel(ylabel, color="#94A3B8", fontsize=8.5)
        ax.tick_params(colors="#94A3B8", labelsize=8)
        ax.grid(True, linestyle="--", alpha=0.2, color="#94A3B8")
        for spine in ax.spines.values():
            spine.set_color("#334155")
        if scenario_choice != "steady_state":
            ax.axvline(x=event_time, color="#EF4444", linestyle=":", alpha=0.7, label="Event Start")

    # Plot 1: Flow and Head
    ax1 = axes[0, 0]
    ax1.plot(t, sim_res.flow_m3s, color="#38BDF8", linewidth=1.8, label="Flow Q (m³/s)")
    ax1_twin = ax1.twinx()
    ax1_twin.plot(t, sim_res.net_head_m, color="#F59E0B", linewidth=1.5, linestyle="--", label="Net Head (m)")
    ax1_twin.set_ylabel("Net Head (m)", color="#F59E0B", fontsize=8.5)
    ax1_twin.tick_params(colors="#F59E0B", labelsize=8)
    for spine in ax1_twin.spines.values():
        spine.set_color("#334155")
    style_ax(ax1, "Hydraulic Flow & Net Head Dynamics", "Flow Rate Q (m³/s)")

    # Plot 2: Speed and Frequency
    ax2 = axes[0, 1]
    ax2.plot(t, sim_res.speed_rpm, color="#10B981", linewidth=1.8, label="Runner Speed (RPM)")
    ax2.axhline(y=turb_params.rated_speed_rpm, color="#94A3B8", linestyle="--", alpha=0.5, label="Synchronous Speed")
    style_ax(ax2, "Runner Rotational Speed & Overspeed Transient", "Rotational Speed (RPM)")
    ax2.legend(loc="upper right", fontsize=7.5, facecolor="#1E293B", edgecolor="#334155", labelcolor="#E2E8F0")

    # Plot 3: Power Outputs
    ax3 = axes[1, 0]
    ax3.plot(t, sim_res.mechanical_power_kw, color="#A855F7", linewidth=1.8, label="Mechanical Shaft Power (kW)")
    ax3.plot(t, sim_res.electrical_power_kw, color="#2563EB", linewidth=1.5, linestyle="-.", label="Electrical Output (kW)")
    style_ax(ax3, "Turbine Mechanical vs Electrical Power Output", "Power (kW)")
    ax3.legend(loc="upper right", fontsize=7.5, facecolor="#1E293B", edgecolor="#334155", labelcolor="#E2E8F0")

    # Plot 4: Gate Position
    ax4 = axes[1, 1]
    ax4.plot(t, sim_res.gate_position_pct, color="#EC4899", linewidth=1.8, label="Gate Opening (%)")
    style_ax(ax4, "Governor Servomotor Gate Stroke Position", "Gate Position (%)")
    ax4.set_ylim(0, 105)

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # Engineering Assumptions & Limitations
    st.markdown("---")
    st.markdown("##### Stated Engineering Assumptions & Physics Model Limits")
    with st.expander("View Governing Equations & Modeling Scope", expanded=False):
        for asm in sim_res.assumptions:
            st.markdown(f"- {asm}")
        st.info(
            "Note: This lumped-parameter model accurately reproduces first-order water column inertia, "
            "governor frequency response, and steady friction. Detailed 3D CFD runner cavitation vortex modeling "
            "and elastic pipe 2D water hammer method-of-characteristics (MOC) are outside desktop lumped ODE scope."
        )

    # Actions: Save Simulation to Database, Export CSV
    act1, act2 = st.columns(2)
    with act1:
        sim_name_input = st.text_input("Simulation Run Label", value=f"{sim_res.scenario_name}_{int(sim_duration)}s")
        if st.button("Save Simulation Record to Project", type="primary"):
            pid = active_project.get("id") if active_project else None
            sid = db.save_simulation(
                project_id=pid,
                scenario_name=sim_name_input,
                params={
                    "duration_s": sim_duration,
                    "event_time_s": event_time,
                    "initial_gate": init_gate_pct,
                    "scenario_type": scenario_choice,
                    "pipe_l": pipe_l,
                    "pipe_d": pipe_d,
                },
                summary=sim_res.to_summary_dict()
            )
            st.success(f"Simulation saved to project records (ID: {sid})!")

    with act2:
        st.markdown("<br/>", unsafe_allow_html=True)
        sim_csv = export_simulation_to_csv(sim_res)
        st.download_button(
            label="📊 Export Simulation Time-Series (CSV)",
            data=sim_csv,
            file_name=f"Simulation_{sim_name_input}.csv",
            mime="text/csv"
        )
