"""Live Telemetry Dashboard with Simulated and Physical MQTT Operating Modes."""

import time
from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from src.database.storage import DatabaseManager
from src.telemetry.sensor_manager import (
    TelemetryDataPoint,
    TelemetryThresholds,
    evaluate_telemetry_point,
)
from src.telemetry.simulated_data import SimulatedTelemetryGenerator
from src.telemetry.mqtt_client import HydroMQTTClient, MQTTConfig


def render_monitoring_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the live monitoring and telemetry stream interface."""
    st.subheader("Live Telemetry & SCADA Monitoring")
    st.caption("Monitor hydraulic parameters, generator electrical measurements, and machinery vibration in real-time.")

    # Initialize session state telemetry buffer
    if "telemetry_buffer" not in st.session_state:
        st.session_state["telemetry_buffer"] = []
    if "sim_generator" not in st.session_state:
        st.session_state["sim_generator"] = SimulatedTelemetryGenerator(
            base_flow_lps=float(active_project.get("design_flow_lps", 1200.0)) if active_project else 1200.0,
            base_head_m=float(active_project.get("gross_head_m", 30.0)) if active_project else 30.0,
        )
    if "stream_active" not in st.session_state:
        st.session_state["stream_active"] = False
    if "mqtt_client_instance" not in st.session_state:
        st.session_state["mqtt_client_instance"] = None

    # Telemetry Source Mode Selector
    source_mode = st.radio(
        "Telemetry Data Source",
        options=["Simulated Telemetry (Offline Synthetic Stream)", "Physical Sensor Integration (MQTT / ESP32 / PLC)"],
        horizontal=True
    )

    is_simulated_mode = "Simulated" in source_mode

    # ==================== MODE 1: SIMULATED TELEMETRY ====================
    if is_simulated_mode:
        st.markdown(
            """
            <div style="background-color: #1E293B; border: 1px solid #2563EB; border-left: 4px solid #38BDF8; padding: 10px 14px; border-radius: 4px; margin-bottom: 15px;">
                <span class="badge badge-simulated">SYNTHETIC SIMULATED TELEMETRY ACTIVE</span>
                <span style="font-size: 0.85rem; color: #CBD5E1; margin-left: 10px;">
                    Readings are synthetically computed using physics-based stochastic turbulence and electrical load equations.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        gen: SimulatedTelemetryGenerator = st.session_state["sim_generator"]

        # Control Toolbar
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        with c1:
            if not st.session_state["stream_active"]:
                if st.button("▶ Start Simulated Stream", type="primary"):
                    st.session_state["stream_active"] = True
                    st.rerun()
            else:
                if st.button("⏹ Stop Stream", type="secondary"):
                    st.session_state["stream_active"] = False
                    st.rerun()

        with c2:
            if st.button("Step 1 New Reading", type="secondary"):
                new_pt = gen.generate_next_point()
                st.session_state["telemetry_buffer"].append(new_pt.to_dict())
                if len(st.session_state["telemetry_buffer"]) > 100:
                    st.session_state["telemetry_buffer"].pop(0)
                # Log to SQLite
                db.log_telemetry_point(
                    source="SIMULATED",
                    flow_lps=new_pt.flow_lps,
                    net_head_m=new_pt.net_head_m,
                    power_kw=new_pt.power_kw,
                    frequency_hz=new_pt.frequency_hz,
                    voltage_v=new_pt.voltage_v,
                    current_a=new_pt.current_a,
                    gate_position_pct=new_pt.gate_position_pct,
                    alerts=new_pt.alerts,
                    project_id=active_project.get("id") if active_project else None
                )
                st.rerun()

        with c3:
            if st.button("Clear Buffer"):
                st.session_state["telemetry_buffer"] = []
                st.rerun()

        with c4:
            auto_step_count = st.selectbox("Batch Readings", options=[1, 5, 10, 25], index=1)
            if st.button("Inject Batch"):
                for _ in range(auto_step_count):
                    pt = gen.generate_next_point()
                    st.session_state["telemetry_buffer"].append(pt.to_dict())
                if len(st.session_state["telemetry_buffer"]) > 150:
                    st.session_state["telemetry_buffer"] = st.session_state["telemetry_buffer"][-150:]
                st.rerun()

        # Disturbance Injection for Operator Training
        with st.expander("Fault & Disturbance Injection (Operator Training)", expanded=False):
            st.caption("Test alarm conditions and operator alert responses by triggering simulated anomalies:")
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                chk_flow = st.checkbox("Simulate Intake Trash Rack Clogging", value=gen.injected_low_flow)
                gen.trigger_disturbance("low_flow", chk_flow)
            with f2:
                chk_freq = st.checkbox("Simulate Grid Frequency Surge (>51 Hz)", value=gen.injected_frequency_trip)
                gen.trigger_disturbance("frequency_trip", chk_freq)
            with f3:
                chk_temp = st.checkbox("Simulate Bearing Lubrication Overheat", value=gen.injected_bearing_fault)
                gen.trigger_disturbance("bearing_fault", chk_temp)
            with f4:
                chk_vib = st.checkbox("Simulate Severe Runner Vibration", value=gen.injected_vibration_spike)
                gen.trigger_disturbance("vibration_spike", chk_vib)

    # ==================== MODE 2: PHYSICAL MQTT INTEGRATION ====================
    else:
        st.markdown(
            """
            <div style="background-color: #1E293B; border: 1px solid #475569; border-left: 4px solid #10B981; padding: 10px 14px; border-radius: 4px; margin-bottom: 15px;">
                <span class="badge badge-physical">PHYSICAL HARDWARE TELEMETRY LAYER</span>
                <span style="font-size: 0.85rem; color: #CBD5E1; margin-left: 10px;">
                    Integration-ready for ESP32 microcontrollers, Arduino IoT transmitters, or industrial PLCs over local MQTT.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander("MQTT Broker & Sensor Channel Configuration", expanded=True):
            mq1, mq2, mq3 = st.columns(3)
            with mq1:
                broker_host = st.text_input("MQTT Broker IP / Hostname", value="localhost")
                broker_port = st.number_input("Broker Port", min_value=1, max_value=65535, value=1883)
            with mq2:
                topic_sub = st.text_input("Telemetry Topic", value="hydropower/telemetry/#")
                client_id = st.text_input("MQTT Client ID", value="HydroPower_Intel_Desktop")
            with mq3:
                auth_user = st.text_input("Username (Optional)", value="")
                auth_pass = st.text_input("Password (Optional)", value="", type="password")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Connect to Local MQTT Broker", type="primary"):
                    cfg = MQTTConfig(
                        broker_host=broker_host,
                        broker_port=int(broker_port),
                        topic=topic_sub,
                        client_id=client_id,
                        username=auth_user if auth_user else None,
                        password=auth_pass if auth_pass else None
                    )
                    client = HydroMQTTClient(config=cfg)
                    client.connect_async()
                    st.session_state["mqtt_client_instance"] = client
                    st.rerun()

            with btn_col2:
                if st.button("Disconnect MQTT"):
                    if st.session_state["mqtt_client_instance"]:
                        st.session_state["mqtt_client_instance"].disconnect()
                        st.session_state["mqtt_client_instance"] = None
                    st.rerun()

        # Check MQTT status
        mqtt_cli = st.session_state.get("mqtt_client_instance")
        if mqtt_cli:
            status_info = mqtt_cli.get_status()
            if status_info["is_connected"]:
                st.success(f"Connected to MQTT Broker: {status_info['broker']} | Topic: {status_info['topic']} | Packets: {status_info['packet_count']}")
                if mqtt_cli.latest_data:
                    st.session_state["telemetry_buffer"].append(mqtt_cli.latest_data.to_dict())
            else:
                st.warning(f"MQTT Client Status: {status_info['status_message']}")
        else:
            st.info("MQTT Client is currently DISCONNECTED. No physical sensors attached (Running offline).")

    # ==================== LIVE DASHBOARD DISPLAY ====================
    # Ensure buffer has at least 1 seed reading if empty
    if not st.session_state["telemetry_buffer"]:
        init_pt = st.session_state["sim_generator"].generate_next_point()
        st.session_state["telemetry_buffer"].append(init_pt.to_dict())

    latest = st.session_state["telemetry_buffer"][-1]

    st.markdown("---")
    st.markdown("#### Live Sensor Transducers & Operating Parameters")

    # Status banner for latest reading
    status_level = latest.get("status_level", "NORMAL")
    if status_level == "ALARM":
        st.error(f"🚨 ALARM STATE: {', '.join(latest.get('alerts', ['System threshold exceeded!']))}")
    elif status_level == "WARNING":
        st.warning(f"⚠️ OPERATING WARNING: {', '.join(latest.get('alerts', ['Review parameters']))}")
    else:
        st.success("✓ Normal Plant Operating Mode: All parameters within standard design envelopes.")

    # 6 Core SCADA Metrics
    g1, g2, g3, g4, g5, g6 = st.columns(6)
    with g1:
        st.metric("Flow Rate", f"{latest['flow_lps']:,.1f} L/s", delta=f"{latest['flow_lps']/1000:.3f} m³/s")
    with g2:
        st.metric("Net Head", f"{latest['net_head_m']:.2f} m", delta="Pressure Transmitter")
    with g3:
        st.metric("Active Power", f"{latest['power_kw']:,.1f} kW", delta=f"{latest['current_a']:.1f} A")
    with g4:
        st.metric("Grid Frequency", f"{latest['frequency_hz']:.2f} Hz", delta="Target: 50.00 Hz")
    with g5:
        st.metric("Bearing Temp", f"{latest['bearing_temp_c']:.1f} °C", delta="Max 70°C", delta_color="inverse" if latest['bearing_temp_c'] > 68 else "normal")
    with g6:
        st.metric("Vibration RMS", f"{latest['vibration_mms']:.2f} mm/s", delta="ISO 10816 Zone B", delta_color="inverse" if latest['vibration_mms'] > 4.5 else "normal")

    # Historical Trend Graphs
    st.markdown("##### Real-Time SCADA Time-Series Trends")
    buf_df = pd.DataFrame(st.session_state["telemetry_buffer"])

    if len(buf_df) >= 2:
        fig, (p1, p2) = plt.subplots(1, 2, figsize=(11, 3.5), facecolor="#1E293B")

        # Plot 1: Power and Flow
        p1.set_facecolor("#0F172A")
        p1.plot(buf_df.index, buf_df["power_kw"], color="#38BDF8", linewidth=1.8, label="Active Power (kW)")
        p1.set_ylabel("Power (kW)", color="#38BDF8", fontsize=8.5)
        p1.set_xlabel("Sample Step", color="#94A3B8", fontsize=8.5)
        p1.tick_params(colors="#94A3B8", labelsize=8)
        p1.grid(True, linestyle="--", alpha=0.2, color="#94A3B8")
        for spine in p1.spines.values():
            spine.set_color("#334155")
        p1.set_title("Generated Power Output", color="#E2E8F0", fontsize=9.5, fontweight="bold")

        # Plot 2: Frequency and Bearing Health
        p2.set_facecolor("#0F172A")
        p2.plot(buf_df.index, buf_df["frequency_hz"], color="#10B981", linewidth=1.8, label="Frequency (Hz)")
        p2.axhline(50.0, color="#94A3B8", linestyle="--", alpha=0.5)
        p2.set_ylabel("Frequency (Hz)", color="#10B981", fontsize=8.5)
        p2.set_xlabel("Sample Step", color="#94A3B8", fontsize=8.5)
        p2.tick_params(colors="#94A3B8", labelsize=8)
        p2.grid(True, linestyle="--", alpha=0.2, color="#94A3B8")
        for spine in p2.spines.values():
            spine.set_color("#334155")
        p2.set_title("Grid Synchronization Frequency", color="#E2E8F0", fontsize=9.5, fontweight="bold")

        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # Historical Log Table
    with st.expander("Recent Telemetry Log Table (Last 15 Packets)", expanded=False):
        st.dataframe(buf_df.tail(15)[["timestamp", "source", "flow_lps", "net_head_m", "power_kw", "frequency_hz", "bearing_temp_c", "vibration_mms", "status_level"]], use_container_width=True, hide_index=True)
