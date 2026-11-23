"""HydroPower Intelligence — Main Application Entry Point.

Desktop-first integrated hydropower engineering application combining:
1. Calculator & Sizing Tool
2. Physics / Control Simulation Lab
3. Real-Time Telemetry Dashboard
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.database.storage import DatabaseManager
from src.components.styles import apply_engineering_theme, render_header
from src.components.dashboard import render_overview_tab
from src.components.project_manager import render_project_manager_tab
from src.components.calculator import render_calculator_tab
from src.components.simulator import render_simulator_tab
from src.components.monitoring import render_monitoring_tab
from src.components.hydrothermal_lab_view import render_hydrothermal_3d_lab_tab
from src.components.analytics_view import render_analytics_tab
from src.components.insights_view import render_insights_tab
from src.components.reports_view import render_reports_tab
from src.components.settings_view import render_settings_tab


# Configure Streamlit page
st.set_page_config(
    page_title="HydroPower Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_app_state() -> DatabaseManager:
    """Initializes local database and session state."""
    if "db_manager" not in st.session_state:
        st.session_state["db_manager"] = DatabaseManager()

    db: DatabaseManager = st.session_state["db_manager"]

    if "active_project" not in st.session_state:
        projects = db.list_projects()
        st.session_state["active_project"] = projects[0] if projects else None

    return db


def main():
    apply_engineering_theme()
    db = init_app_state()

    active_project = st.session_state.get("active_project")
    proj_name = active_project.get("name", "No Project Selected") if active_project else "No Project Selected"

    render_header(proj_name)

    # Sidebar Navigation
    with st.sidebar:
        st.markdown("### ⚡ HYDROPOWER INTELLIGENCE")
        st.caption("Desktop Engineering Suite v1.0")
        st.markdown("---")

        nav_section = st.radio(
            "Engineering Modules",
            options=[
                "Overview",
                "Project Manager",
                "Power Calculator",
                "Simulation Lab",
                "Live Telemetry",
                "Hydrothermal & 3D Lab",
                "Analytics & Sensitivity",
                "Engineering Insights",
                "Reports & Exports",
                "System Configuration"
            ],
            index=0
        )

        st.markdown("---")
        st.markdown("##### Plant Selection")
        projects = db.list_projects()
        if projects:
            p_names = [p["name"] for p in projects]
            curr_idx = p_names.index(proj_name) if proj_name in p_names else 0
            selected_proj_name = st.selectbox("Active Plant", options=p_names, index=curr_idx)
            if selected_proj_name != proj_name:
                st.session_state["active_project"] = db.get_project_by_name(selected_proj_name)
                st.rerun()

        st.markdown("---")
        st.markdown(
            """
            <div style="font-size: 0.75rem; color: #94A3B8; line-height: 1.5;">
                <b>System Status:</b><br/>
                • Operating Mode: <span style="color: #34D399;">Offline Local</span><br/>
                • Storage: <span style="color: #60A5FA;">SQLite Embedded</span><br/>
                • Solvers: <span style="color: #F8FAFC;">NumPy / SciPy</span><br/>
                • Telemetry: <span style="color: #FBBF24;">Synthetic / MQTT</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Route to Section Component
    if nav_section == "Overview":
        render_overview_tab(db, active_project)
    elif nav_section == "Project Manager":
        st.session_state["active_project"] = render_project_manager_tab(db, active_project)
    elif nav_section == "Power Calculator":
        render_calculator_tab(db, active_project)
    elif nav_section == "Simulation Lab":
        render_simulator_tab(db, active_project)
    elif nav_section == "Live Telemetry":
        render_monitoring_tab(db, active_project)
    elif nav_section == "Hydrothermal & 3D Lab":
        render_hydrothermal_3d_lab_tab(db, active_project)
    elif nav_section == "Analytics & Sensitivity":
        render_analytics_tab(db, active_project)
    elif nav_section == "Engineering Insights":
        render_insights_tab(db, active_project)
    elif nav_section == "Reports & Exports":
        render_reports_tab(db, active_project)
    elif nav_section == "System Configuration":
        render_settings_tab(db)


if __name__ == "__main__":
    main()
