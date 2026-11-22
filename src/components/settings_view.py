"""System configuration, physical constants, unit preferences, and local database management."""

import os
from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd

from src.database.storage import DatabaseManager


def render_settings_tab(db: DatabaseManager) -> None:
    """Renders application settings, unit configurations, and database diagnostics."""
    st.subheader("System Configuration & Preferences")
    st.caption("Configure default physical parameters, simulation solver tolerances, and inspect local SQLite database.")

    set1, set2, set3 = st.tabs(["Engineering Constants & Units", "Telemetry & MQTT Defaults", "Local Database & Storage Diagnostics"])

    # 1. Physical Constants & Units
    with set1:
        st.markdown("##### Default Hydraulic & Environmental Constants")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Freshwater Density ρ (kg/m³)", value=1000.0, disabled=True, help="Standard density of fresh water at 4°C-20°C.")
            st.number_input("Gravitational Acceleration g (m/s²)", value=9.81, disabled=True, help="Standard terrestrial acceleration due to gravity (WGS 84 sea level standard).")
            st.number_input("Kinematic Viscosity of Water ν at 20°C (m²/s)", value=1.004e-6, format="%.3e", disabled=True)
        with c2:
            st.selectbox("Default Flow Display Unit", options=["L/s (Litres/second)", "m³/s (Cubic metres/sec)"], index=0)
            st.selectbox("Head & Elevation Unit", options=["Metres (m)"], index=0)
            st.selectbox("Power Unit", options=["Kilowatts (kW)", "Megawatts (MW)"], index=0)
            st.selectbox("Energy Unit", options=["Kilowatt-hours (kWh)", "Megawatt-hours (MWh)"], index=0)

    # 2. Telemetry Defaults
    with set2:
        st.markdown("##### Default SCADA & MQTT Broker Configuration")
        m1, m2 = st.columns(2)
        with m1:
            st.text_input("Default Broker Address", value="localhost")
            st.number_input("Default Broker Port", value=1883)
        with m2:
            st.text_input("Default Topic Prefix", value="hydropower/telemetry/#")
            st.number_input("Sampling Interval (seconds)", value=1.0, min_value=0.1, max_value=60.0)

    # 3. Database Diagnostics
    with set3:
        st.markdown("##### Local SQLite Database Diagnostics")
        db_path = db.db_path
        exists = os.path.exists(db_path)
        file_size_kb = os.path.getsize(db_path) / 1024.0 if exists else 0.0

        st.write(f"**Database Location:** `{db_path}`")
        st.write(f"**Database Size on Disk:** `{file_size_kb:.2f} KB`")

        projects = db.list_projects()
        all_calcs = db.list_calculations()
        all_sims = db.list_simulations()
        telemetry_logs = db.get_recent_telemetry(limit=500)

        diag_df = pd.DataFrame([
            {"Table": "projects", "Record Count": len(projects), "Purpose": "Hydropower plant records & civil parameters"},
            {"Table": "calculations", "Record Count": len(all_calcs), "Purpose": "Power calculator sizing snapshots"},
            {"Table": "simulations", "Record Count": len(all_sims), "Purpose": "Dynamic simulation runs & transient summaries"},
            {"Table": "telemetry_logs", "Record Count": len(telemetry_logs), "Purpose": "Historical sensor time-series records"},
            {"Table": "app_settings", "Record Count": 2, "Purpose": "Local preferences & broker cache"},
        ])
        st.table(diag_df)

        st.info("All project data, calculations, and simulation models are stored locally and run completely offline.")
