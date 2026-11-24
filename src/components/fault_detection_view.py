"""Digital Twin Fault Detection & Diagnostics Centre View."""

from typing import Any, Dict, List, Optional
import streamlit as st

from src.database.storage import DatabaseManager
from src.diagnostics.engine import FaultEngine, FaultSeverity, FaultType
from src.cad.sensor_mesh_mapper import SensorMeshMapper


def render_fault_detection_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the Digital Twin Fault Detection, Statistical Anomaly, and Explainable Diagnostics view."""
    st.subheader("Fault Detection & Diagnostics Centre")
    st.caption("Coupled multi-level engineering fault detection connecting real sensors, hydraulic simulations, and 3D sub-components.")

    p_id = active_project.get("id") if active_project else None

    # Initialize Engine
    if "fault_engine" not in st.session_state:
        st.session_state["fault_engine"] = FaultEngine(db_manager=db)
    engine: FaultEngine = st.session_state["fault_engine"]

    tab_active, tab_level2, tab_level3, tab_rules, tab_demo = st.tabs([
        "1. Active Alerts & 3D Highlighting",
        "2. Level 2 Statistical Anomaly Screening",
        "3. Level 3 Explainable Diagnostics",
        "4. Sensor Threshold Rules",
        "5. Controlled Fault Demonstration"
    ])

    # =========================================================================
    # TAB 1: ACTIVE ALERTS & 3D HIGHLIGHTING
    # =========================================================================
    with tab_active:
        st.markdown("##### Active Component Faults")
        alerts = list(engine.active_alerts.values())

        if not alerts:
            st.success("✓ **All Systems Nominal:** No active mechanical, hydraulic, or structural faults detected.")
        else:
            for alert in alerts:
                is_crit = alert.severity == FaultSeverity.CRITICAL.value
                box_color = "#EF4444" if is_crit else "#F59E0B"
                badge_class = "badge-alarm" if is_crit else "badge-warning"

                st.markdown(
                    f"""
                    <div style="background: #1E293B; border-left: 4px solid {box_color}; padding: 10px 14px; border-radius: 6px; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 700; color: #FFF; font-size: 13px;">{alert.message}</span>
                            <span class="badge {badge_class}">{alert.severity} • {alert.fault_type}</span>
                        </div>
                        <div style="font-size: 11px; color: #94A3B8; margin-top: 5px;">
                            Sensor: <code>{alert.sensor_id}</code> | 3D Target: <code>{alert.component_id}</code> |
                            Measured: <b style="color: #FFF;">{alert.measured_value:.2f} {alert.unit}</b> (Limit: {alert.threshold_value:.2f} {alert.unit}) |
                            Timestamp: {alert.timestamp[:19]}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    if st.button("Acknowledge & Clear", key=f"clr_{alert.sensor_id}"):
                        engine.clear_alert(alert.sensor_id)
                        st.rerun()

    # =========================================================================
    # TAB 2: LEVEL 2 STATISTICAL ANOMALY SCREENING
    # =========================================================================
    with tab_level2:
        st.markdown("##### Level 2: Historical Statistical Anomaly Detection")
        st.caption("Identifies subtle sensor drift, high-frequency turbulence, and bearing wear using rolling Z-scores without heavy ML overhead.")

        selected_sensor = st.selectbox(
            "Select Telemetry Stream to Inspect",
            options=["SCADA_TURB1_VIB_X", "HECRAS_GATE02_PRESS", "IOT_DAM_CRACK_09", "SCADA_BEARING_TEMP_01"],
            index=0
        )

        history = list(engine.history_windows.get(selected_sensor, []))
        if len(history) < 5:
            st.info(f"Insufficient history samples in sliding window for `{selected_sensor}`. Run virtual or hardware turbine to accumulate data.")
        else:
            mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            std = variance ** 0.5
            curr = history[-1]
            z_score = abs(curr - mean) / max(1e-4, std)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Value", f"{curr:.2f}")
            c2.metric("Window Mean (μ)", f"{mean:.2f}")
            c3.metric("Std Dev (σ)", f"{std:.3f}")
            c4.metric("Active Z-Score", f"{z_score:.2f} σ")

            st.line_chart(history)

    # =========================================================================
    # TAB 3: LEVEL 3 EXPLAINABLE DIAGNOSTICS
    # =========================================================================
    with tab_level3:
        st.markdown("##### Level 3: Physics-Grounded Explainable Diagnostics")
        st.caption("Explain active alerts with engineering root-cause hypotheses, physical principles, and prioritized inspection checklists.")

        if not alerts:
            st.info("No active alerts to diagnose. Inject a fault scenario in Tab 5 to preview diagnostic reasoning.")
        else:
            for alert in alerts:
                diag = alert.diagnostics
                with st.expander(f"🔍 Diagnostic Dossier: {alert.sensor_id} ({alert.component_id})", expanded=True):
                    st.markdown(f"**Diagnostic Summary:** {diag.summary}")
                    st.markdown(f"**Physical Governing Principle:** ` {diag.governing_equation} `")
                    st.metric("Confidence Level", f"{diag.confidence_pct:.0f}%")

                    st.markdown("###### Potential Root Causes:")
                    for cause in diag.potential_causes:
                        st.write(f"• {cause}")

                    st.markdown("###### Prioritized Inspection Steps:")
                    for i, step in enumerate(diag.inspection_steps, 1):
                        st.write(f"**{i}.** {step}")

    # =========================================================================
    # TAB 4: SENSOR THRESHOLD RULES
    # =========================================================================
    with tab_rules:
        st.markdown("##### Configurable Sensor Safety Thresholds")
        mappings = db.list_sensor_mappings(project_id=p_id)

        rule_table = []
        for m in mappings:
            rule_table.append({
                "Sensor Tag": m["sensor_id"],
                "Sensor Name": m["sensor_name"],
                "Target 3D Component": m["component_id"],
                "Warning Limit": f"{m['warning_threshold']} {m['unit']}",
                "Critical Limit": f"{m['critical_threshold']} {m['unit']}",
                "Comparison": m.get("comparison_op", ">")
            })
        st.dataframe(rule_table, use_container_width=True)

    # =========================================================================
    # TAB 5: CONTROLLED FAULT DEMONSTRATION
    # =========================================================================
    with tab_demo:
        st.markdown("##### Fault Demonstration & Educational Testing")
        st.caption("Inject controlled, clearly-labelled simulated faults to demonstrate 3D camera fly-to, emissive alerting, and X-ray isolation.")

        d_col1, d_col2 = st.columns([1.5, 1.0])

        with d_col1:
            scenario_choice = st.selectbox(
                "Select Fault Scenario to Inject",
                options=[
                    ("vibration_spike", "Runner Shaft High Vibration (Unbalance / Cavitation)"),
                    ("gate_pressure_surge", "Intake Sluice Gate Hydrostatic Pressure Surge"),
                    ("dam_crest_crack", "Dam Crest Contraction Joint Displacement"),
                    ("bearing_overheat", "Generator Main Thrust Bearing Overheat"),
                    ("compound_emergency", "Compound Emergency (Multi-Subsystem Alarm)")
                ],
                format_func=lambda x: x[1]
            )

            if st.button("🚨 Inject Simulated Fault Scenario", type="primary"):
                engine.inject_simulated_fault(scenario_choice[0], project_id=p_id)
                st.success(f"Injected scenario: **{scenario_choice[1]}**. View 3D response in the Digital Twin (JARVIS 3D) view.")
                st.rerun()

        with d_col2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("⟲ Clear All Simulated Faults (Reset)", type="secondary"):
                cleared = engine.clear_all_simulated_faults()
                st.success(f"Cleared {cleared} simulated fault alerts.")
                st.rerun()
