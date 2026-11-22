"""Power Calculator and Hydraulic Sizing Workspace."""

from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from src.database.storage import DatabaseManager
from src.engine.hydropower import (
    calculate_comprehensive_hydropower,
    HydropowerCalculationResult,
)
from src.engine.head_loss import PIPE_MATERIALS, FITTING_K_VALUES
from src.analytics.reports import generate_pdf_report, export_calculation_to_csv


def render_calculator_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the comprehensive hydropower calculator workspace."""
    st.subheader("Power Calculator & Hydraulic Sizing Tool")
    st.caption("Calculate hydraulic head loss, effective net head, electrical power generation, and turbine regime.")

    # Defaults from active project
    default_head = float(active_project.get("gross_head_m", 25.0)) if active_project else 25.0
    default_flow = float(active_project.get("design_flow_lps", 1000.0)) if active_project else 1000.0
    default_eff = float(active_project.get("efficiency", 0.82) * 100.0) if active_project else 82.0
    default_diam = float(active_project.get("pipe_diameter_m", 0.50)) if active_project else 0.50
    default_len = float(active_project.get("pipe_length_m", 150.0)) if active_project else 150.0

    # Input Form Layout
    with st.expander("Hydraulic & Electromechanical Input Parameters", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("###### 1. Water Movement (Flow)")
            flow_unit = st.radio("Flow Unit", options=["L/s (Litres/second)", "m³/s (Cubic metres/sec)"], horizontal=True)
            if "L/s" in flow_unit:
                in_flow_lps = st.number_input(
                    "Flow Rate (L/s)",
                    min_value=0.0,
                    max_value=500000.0,
                    value=default_flow,
                    step=10.0,
                    help="Volumetric river discharge directed into the intake penstock."
                )
                flow_lps = in_flow_lps
                flow_m3s = None
            else:
                in_flow_m3s = st.number_input(
                    "Flow Rate (m³/s)",
                    min_value=0.0,
                    max_value=500.0,
                    value=default_flow / 1000.0,
                    step=0.05,
                    help="Volumetric flow rate in cubic metres per second."
                )
                flow_m3s = in_flow_m3s
                flow_lps = None

            gross_head = st.number_input(
                "Gross Head (m)",
                min_value=0.1,
                max_value=2500.0,
                value=default_head,
                step=0.5,
                help="Vertical elevation drop between intake water level and turbine discharge tailrace."
            )

        with col2:
            st.markdown("###### 2. Hydraulic Friction Method")
            loss_method = st.selectbox(
                "Head Loss Formulation",
                options=["Darcy-Weisbach (Rigorous Colebrook)", "Hazen-Williams (Empirical)", "Manual Head Loss Input"],
                index=0,
                help="Darcy-Weisbach is the recommended theoretical formulation across all diameters and velocities."
            )

            if "Manual" in loss_method:
                manual_loss = st.number_input(
                    "Manual Head Loss (m)",
                    min_value=0.0,
                    max_value=gross_head * 0.95,
                    value=min(2.0, gross_head * 0.1),
                    step=0.1,
                    help="User-defined static head loss in metres."
                )
                method_key = "manual"
                pipe_d = None
                pipe_l = None
                mat_roughness = 0.045
                c_factor = 130.0
                fittings_list = []
            else:
                method_key = "darcy_weisbach" if "Darcy" in loss_method else "hazen_williams"
                manual_loss = 0.0

                pipe_d = st.number_input(
                    "Internal Pipe Diameter D (m)",
                    min_value=0.02,
                    max_value=12.0,
                    value=default_diam,
                    step=0.05,
                    help="Inside diameter of the penstock pipe (e.g. 0.50 m = 500 mm)."
                )

                pipe_l = st.number_input(
                    "Penstock Length L (m)",
                    min_value=1.0,
                    max_value=25000.0,
                    value=default_len,
                    step=5.0,
                    help="Total developed length of penstock from intake to turbine casing."
                )

                mat_choice = st.selectbox(
                    "Pipe Material / Lining",
                    options=list(PIPE_MATERIALS.keys()),
                    format_func=lambda k: PIPE_MATERIALS[k].name,
                    index=1
                )
                mat_roughness = PIPE_MATERIALS[mat_choice].roughness_mm
                c_factor = PIPE_MATERIALS[mat_choice].hazen_williams_c

        with col3:
            st.markdown("###### 3. Turbine & Operating Duration")
            eff_pct = st.number_input(
                "Overall Efficiency η (%)",
                min_value=10.0,
                max_value=98.0,
                value=default_eff,
                step=0.5,
                help="Water-to-wire combined efficiency (Turbine runner × Generator × Transformer)."
            )
            efficiency = eff_pct / 100.0

            hours = st.number_input(
                "Operating Duration (hours)",
                min_value=0.5,
                max_value=8760.0,
                value=24.0,
                step=1.0,
                help="Evaluation time window for cumulative electrical energy production."
            )

            cap_factor = st.slider(
                "Annual Capacity Factor (CF)",
                min_value=0.40,
                max_value=1.00,
                value=0.85,
                step=0.05,
                help="Expected plant availability accounting for seasonal low-flow periods and maintenance."
            )

    # Minor fittings expander
    fittings_list = []
    if method_key in ("darcy_weisbach", "hazen_williams"):
        with st.expander("Penstock Minor Losses (Bends, Valves & Entrance Fittings)", expanded=False):
            st.caption("Select quantities for valves, elbows, and transitions (hm = ΣK · v² / 2g):")
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                intake_type = st.selectbox(
                    "Intake Type",
                    options=["entrance_bellmouth", "entrance_flush", "entrance_projecting"],
                    format_func=lambda k: FITTING_K_VALUES[k][0],
                    index=0
                )
                fittings_list.append((intake_type, 1))

                qty_gate_valve = st.number_input("Gate Valves (Open)", min_value=0, max_value=10, value=1)
                if qty_gate_valve > 0:
                    fittings_list.append(("valve_gate_open", qty_gate_valve))

            with m_col2:
                qty_bend_90 = st.number_input("90° Standard Bends", min_value=0, max_value=20, value=2)
                if qty_bend_90 > 0:
                    fittings_list.append(("bend_90_standard", qty_bend_90))

                qty_bend_45 = st.number_input("45° Bends", min_value=0, max_value=20, value=1)
                if qty_bend_45 > 0:
                    fittings_list.append(("bend_45_standard", qty_bend_45))

            with m_col3:
                qty_check_valve = st.number_input("Check / Non-Return Valves", min_value=0, max_value=5, value=0)
                if qty_check_valve > 0:
                    fittings_list.append(("valve_check_swing", qty_check_valve))

                include_exit = st.checkbox("Submerged Tailrace Exit (K = 1.0)", value=True)
                if include_exit:
                    fittings_list.append(("exit_submerged", 1))

    # Perform Calculation
    try:
        calc_result: HydropowerCalculationResult = calculate_comprehensive_hydropower(
            flow_lps=flow_lps,
            flow_m3s=flow_m3s,
            gross_head_m=gross_head,
            loss_method=method_key,
            manual_head_loss_m=manual_loss,
            pipe_diameter_m=pipe_d,
            pipe_length_m=pipe_l,
            roughness_mm=mat_roughness,
            c_factor=c_factor,
            minor_fittings=fittings_list,
            efficiency=efficiency,
            hours=hours,
            capacity_factor=cap_factor,
        )
    except Exception as e:
        st.error(f"Calculation Error: {e}")
        return

    # Warnings (if any)
    for w in calc_result.warnings:
        st.warning(f"⚠️ {w}")

    # Primary Results Metric Bar
    st.markdown("#### Primary Calculation Results")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Effective Net Head", f"{calc_result.net_head_m:.2f} m", delta=f"-{calc_result.head_loss_m:.2f} m Loss", delta_color="inverse")
    with m2:
        st.metric("Hydraulic Power", f"{calc_result.hydraulic_power_kw:,.1f} kW", delta="100% Potential")
    with m3:
        st.metric("Electrical Power", f"{calc_result.electrical_power_kw:,.1f} kW", delta=f"η = {calc_result.efficiency*100:.1f}%")
    with m4:
        st.metric(f"Energy ({hours:.0f}h)", f"{calc_result.energy_kwh:,.1f} kWh", delta=f"{calc_result.daily_energy_kwh:,.0f} kWh/day")
    with m5:
        st.metric("Annual Forecast", f"{calc_result.annual_energy_mwh:,.1f} MWh/yr", delta=f"CF: {cap_factor*100:.0f}%")

    # Step-by-Step Mathematical Transparency
    st.markdown("---")
    res_col1, res_col2 = st.columns([1.1, 0.9])

    with res_col1:
        st.markdown("##### Mathematical Step-by-Step Substitution")
        for step in calc_result.substitution_steps:
            st.markdown(
                f"""
                <div class="formula-box">
                    <span style="color: #60A5FA; font-weight: bold;">{step['step']}</span><br/>
                    <span style="color: #94A3B8;">Formula:</span> <code>{step['formula']}</code><br/>
                    <span style="color: #94A3B8;">Substituted:</span> {step['substitution']} &rarr; <b>{step['result']}</b>
                </div>
                """,
                unsafe_allow_html=True
            )

    with res_col2:
        st.markdown("##### Turbine Regime Classification")
        if calc_result.turbine_selection:
            ts = calc_result.turbine_selection
            st.markdown(
                f"""
                <div class="eng-card">
                    <div class="eng-card-title">Recommended Runner: {ts.primary_recommendation}</div>
                    <p style="font-size: 0.85rem; color: #CBD5E1;">{ts.description}</p>
                    <div style="font-size: 0.8rem; margin-bottom: 8px;">
                        <b>Operating Regime:</b> <span class="badge badge-simulated">{ts.regime_category}</span><br/>
                        <b>Metric Specific Speed Ns:</b> <code>{ts.metric_specific_speed_ns}</code><br/>
                        <b>Recommended Generator Speed:</b> <code>{ts.recommended_rpm} RPM</code><br/>
                        <b>Cavitation Risk:</b> {ts.cavitation_risk}
                    </div>
                    <div style="font-size: 0.8rem; color: #94A3B8;">
                        <b>Alternative Options:</b> {', '.join(ts.secondary_options)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        if calc_result.loss_breakdown:
            lb = calc_result.loss_breakdown
            st.markdown("##### Penstock Fluid Dynamics")
            dyn_df = pd.DataFrame([
                {"Parameter": "Flow Velocity v", "Value": f"{lb.flow_velocity_mps:.2f} m/s"},
                {"Parameter": "Velocity Head v²/2g", "Value": f"{lb.velocity_head_m:.4f} m"},
                {"Parameter": "Reynolds Number Re", "Value": f"{lb.reynolds_number:,.0f}"},
                {"Parameter": "Flow Regime", "Value": lb.flow_regime},
                {"Parameter": "Darcy Friction Factor f", "Value": f"{lb.friction_factor:.4f}" if lb.friction_factor > 0 else "N/A"},
                {"Parameter": "Friction Loss hf", "Value": f"{lb.friction_loss_m:.3f} m"},
                {"Parameter": "Minor Fittings Loss hm", "Value": f"{lb.minor_losses_m:.3f} m"},
            ])
            st.table(dyn_df)

    # Actions: Save to Project Database, Download PDF, Export CSV
    st.markdown("---")
    act_col1, act_col2, act_col3 = st.columns(3)

    with act_col1:
        calc_name = st.text_input("Calculation Run Name", value=f"Run_{calc_result.flow_lps:.0f}Lps_{calc_result.gross_head_m:.0f}m")
        if st.button("Save Calculation to Project", type="primary"):
            pid = active_project.get("id") if active_project else None
            cid = db.save_calculation(
                project_id=pid,
                name=calc_name,
                inputs={
                    "flow_lps": calc_result.flow_lps,
                    "gross_head_m": calc_result.gross_head_m,
                    "efficiency": calc_result.efficiency,
                    "loss_method": method_key,
                    "pipe_diameter_m": pipe_d,
                    "pipe_length_m": pipe_l,
                },
                results=calc_result.to_dict(),
                notes=f"Saved from Power Calculator workspace for {active_project.get('name') if active_project else 'Scheme'}."
            )
            st.success(f"Calculation '{calc_name}' saved to SQLite database (ID: {cid})!")

    with act_col2:
        st.markdown("<br/>", unsafe_allow_html=True)
        pdf_bytes = generate_pdf_report(
            calc=calc_result,
            project_name=active_project.get("name", "Hydropower Scheme") if active_project else "Hydropower Scheme",
            location=active_project.get("location", "Civil Site") if active_project else "Site",
            river_name=active_project.get("river_name", "Waterway") if active_project else "River"
        )
        st.download_button(
            label="📄 Download PDF Engineering Report",
            data=pdf_bytes,
            file_name=f"Hydropower_Report_{calc_name}.pdf",
            mime="application/pdf"
        )

    with act_col3:
        st.markdown("<br/>", unsafe_allow_html=True)
        csv_data = export_calculation_to_csv(
            calc_result,
            active_project.get("name", "Hydropower Scheme") if active_project else "Hydropower Scheme"
        )
        st.download_button(
            label="📊 Export Results to CSV",
            data=csv_data,
            file_name=f"Hydropower_Data_{calc_name}.csv",
            mime="text/csv"
        )
