"""Physical Hydropower Turbine Lab View: Hardware Connection, Telemetry, and Digital Twin Binding."""

from typing import Any, Dict, List, Optional
import streamlit as st

from src.database.storage import DatabaseManager
from src.hardware.turbine_interface import PhysicalTurbineManager, OperatingMode, TurbineTelemetryPacket
from src.engine.shared_data import SharedEngineeringContext
from src.components.jarvis_viewer import render_jarvis_viewer
from src.geometry.mesh_builder import PlantGeometryBuilder


def render_physical_turbine_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the hardware-ready Physical Hydropower Turbine Lab."""
    st.subheader("Physical Hydropower Turbine Lab")
    st.caption("Hardware-agnostic digital twin connecting physical micro-controllers (ESP32/PLC) or virtual turbines to live calculations and 3D visualization.")

    # Initialize manager in session state
    if "turbine_manager" not in st.session_state:
        st.session_state["turbine_manager"] = PhysicalTurbineManager(db_manager=db)
    manager: PhysicalTurbineManager = st.session_state["turbine_manager"]

    tab_control, tab_telemetry, tab_digital_twin, tab_fault_demo = st.tabs([
        "1. Hardware & Operating Mode",
        "2. Live Telemetry & Calculations",
        "3. Live 3D Digital Twin",
        "4. Hardware Fault Demonstration"
    ])

    # =========================================================================
    # TAB 1: HARDWARE & OPERATING MODE
    # =========================================================================
    with tab_control:
        st.markdown("##### Operating Mode & Device Connection")

        c_mode1, c_mode2 = st.columns([1.5, 1.0])

        with c_mode1:
            curr_mode = manager.operating_mode.value
            selected_mode = st.radio(
                "Select Operating Mode",
                options=["VIRTUAL", "HARDWARE", "HYBRID"],
                format_func=lambda m: {
                    "VIRTUAL": "1. VIRTUAL MODE — Simulated turbine operation (No hardware required)",
                    "HARDWARE": "2. HARDWARE MODE — Real physical measurements from connected ESP32 / PLC",
                    "HYBRID": "3. HYBRID MODE — Real measurements compared against hydraulic calculations"
                }[m],
                index=["VIRTUAL", "HARDWARE", "HYBRID"].index(curr_mode)
            )
            if selected_mode != curr_mode:
                manager.set_operating_mode(selected_mode)
                st.rerun()

        with c_mode2:
            st.markdown(
                f"""
                <div style="background: #1E293B; border-left: 3px solid #10B981; padding: 10px 14px; border-radius: 4px; font-size: 11px;">
                    <b>Connection Status:</b><br/>
                    • State: <span style="color: {'#10B981' if manager.is_connected else '#FBBF24'};">{manager.connection_status}</span><br/>
                    • Hardware Port: <code>{manager.serial_port}</code><br/>
                    • Protocol: <b>{manager.connection_type}</b><br/>
                    • Telemetry Sync: <b>Active</b>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("---")
        st.markdown("##### Microcontroller / PLC Serial Interface")

        s1, s2, s3 = st.columns(3)
        with s1:
            port_input = st.text_input("Serial COM Port", value=manager.serial_port)
        with s2:
            baud_input = st.selectbox("Baud Rate", options=[9600, 57600, 115200, 230400, 921600], index=2)
        with s3:
            st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
            if not manager.is_connected:
                if st.button("🔌 Connect Hardware", type="primary"):
                    ok, msg = manager.connect_serial_hardware(port_input, baud_input)
                    if ok:
                        st.success(msg)
                    else:
                        st.warning(msg)
                    st.rerun()
            else:
                if st.button("Disconnect Hardware", type="secondary"):
                    manager.disconnect_hardware()
                    st.rerun()

        if manager.operating_mode == OperatingMode.VIRTUAL:
            st.markdown("---")
            st.markdown("##### Virtual Turbine Hydraulic Setpoints")
            v1, v2, v3 = st.columns(3)
            with v1:
                manager.virtual_flow_lps = st.slider("Virtual Water Flow (L/s)", 100.0, 3000.0, manager.virtual_flow_lps, 50.0)
            with v2:
                manager.virtual_gross_head_m = st.slider("Virtual Gross Head (m)", 5.0, 80.0, manager.virtual_gross_head_m, 1.0)
            with v3:
                manager.virtual_gate_pct = st.slider("Guide Vane Opening (%)", 10.0, 100.0, manager.virtual_gate_pct, 5.0)

    # Pull current telemetry packet
    packet = manager.update_telemetry()
    st.session_state["physical_turbine_packet"] = packet

    # =========================================================================
    # TAB 2: LIVE TELEMETRY & CALCULATIONS
    # =========================================================================
    with tab_telemetry:
        st.markdown(f"##### Live Telemetry Stream — `{packet.operating_mode}` Mode")

        # Top Metric Cards
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Water Flow Rate", f"{packet.flow_lps:.1f} L/s", f"{packet.flow_lps/1000:.3f} m³/s")
        m2.metric("Effective Net Head", f"{packet.net_head_m:.1f} m", f"P = {packet.pressure_kpa:.0f} kPa")
        m3.metric("Electrical Power Output", f"{packet.electrical_power_kw:.1f} kW", f"{packet.voltage_v:.0f}V / {packet.current_a:.0f}A")
        m4.metric("Runner Rotational Speed", f"{packet.runner_rpm:.0f} RPM", f"{packet.frequency_hz:.2f} Hz")

        m5, m6, m7, m8 = st.columns(4)
        m5.metric("Shaft Vibration (RMS)", f"{packet.vibration_mms:.2f} mm/s", "ISO 10816 Zone A/B" if packet.vibration_mms < 4.5 else "Elevated")
        m6.metric("Bearing Temperature", f"{packet.bearing_temp_c:.1f} °C", "Nominal" if packet.bearing_temp_c < 65.0 else "High")
        m7.metric("Water-to-Wire Efficiency", f"{packet.water_to_wire_efficiency * 100:.1f} %", "Design Peak: 88%")
        m8.metric("Theoretical Hydraulic Power", f"{packet.theoretical_power_kw:.1f} kW", f"ρ·g·Q·Hnet")

        # Theoretical vs Measured Power Comparison
        st.markdown("---")
        st.markdown("##### Theoretical Hydraulic vs Measured Electrical Performance")
        c_perf1, c_perf2 = st.columns([1.5, 1.0])

        with c_perf1:
            st.markdown(
                f"""
                <div style="background: #1E293B; border: 1px solid #334155; padding: 12px 16px; border-radius: 6px; font-size: 12px;">
                    <b>Hydraulic Power Formulation:</b><br/>
                    <code>P_hydraulic = ρ × g × Q × H_net = 1000 × 9.81 × {packet.flow_lps/1000:.3f} × {packet.net_head_m:.2f} = {packet.theoretical_power_kw:.2f} kW</code><br/><br/>
                    <b>Measured Generator Output:</b><br/>
                    <code>P_electrical = √3 × V × I × cos(φ) = √3 × {packet.voltage_v:.1f} × {packet.current_a:.1f} × {packet.power_factor} = {packet.electrical_power_kw:.2f} kW</code><br/><br/>
                    <b>System Water-to-Wire Efficiency:</b><br/>
                    <code>η = P_electrical / P_hydraulic = {packet.water_to_wire_efficiency * 100:.1f} %</code>
                </div>
                """,
                unsafe_allow_html=True
            )

        with c_perf2:
            st.metric(
                "Efficiency Discrepancy",
                f"{packet.efficiency_discrepancy_pct:+.1f} %",
                "Against Design Baseline"
            )

    # =========================================================================
    # TAB 3: LIVE 3D DIGITAL TWIN
    # =========================================================================
    with tab_digital_twin:
        st.markdown("##### Live 3D Turbine Digital Twin Synchronization")

        # Build shared context for viewer
        ctx_twin = SharedEngineeringContext(
            flow_lps=packet.flow_lps,
            gross_head_m=packet.gross_head_m,
            net_head_m=packet.net_head_m,
            electrical_power_kw=packet.electrical_power_kw,
            runner_speed_rpm=packet.runner_rpm,
            frequency_hz=packet.frequency_hz,
            data_provenance=f"PHYSICAL_TURBINE_{packet.operating_mode}"
        )

        render_jarvis_viewer(
            context=ctx_twin,
            builder=PlantGeometryBuilder(gross_head_m=packet.gross_head_m, include_bridge=True),
            mode="FLOW",
            fault_payloads=packet.active_alerts,
            height=660
        )

    # =========================================================================
    # TAB 4: HARDWARE FAULT DEMONSTRATION
    # =========================================================================
    with tab_fault_demo:
        st.markdown("##### Controlled Hardware Fault Demonstration")
        st.caption("Demonstrate sensor failure, bearing unbalance, and hydraulic surge response without risking physical equipment.")

        d_col1, d_col2 = st.columns([1.5, 1.0])

        with d_col1:
            fault_choice = st.selectbox(
                "Select Fault Injection Scenario",
                options=[
                    ("vibration_spike", "Runner Shaft High Vibration (Unbalance)"),
                    ("bearing_overheat", "Loss of Lubrication / Bearing Overheat"),
                    ("reduced_flow", "Intake Trash Rack Blockage (Low Flow)"),
                    ("pressure_surge", "Penstock Water Hammer Pressure Surge")
                ],
                format_func=lambda x: x[1]
            )

            if st.button("🚨 Inject Scenario into Turbine Model", type="primary"):
                manager.inject_demonstration_scenario(fault_choice[0])
                st.success(f"Injected: **{fault_choice[1]}** [SIMULATED]")
                st.rerun()

        with d_col2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("⟲ Reset Turbine to Nominal", type="secondary"):
                manager.reset_demonstration()
                st.success("Turbine reset to nominal operation.")
                st.rerun()
