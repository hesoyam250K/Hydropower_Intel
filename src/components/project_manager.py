"""Hydropower Project Manager interface for creating, loading, editing, and managing schemes."""

from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd

from src.database.storage import DatabaseManager
from src.engine.head_loss import PIPE_MATERIALS


def render_project_manager_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Renders the Project Manager section."""
    st.subheader("Project Manager")
    st.caption("Manage hydropower site records, civil design parameters, and local SQLite data persistence.")

    projects = db.list_projects()
    project_names = [p["name"] for p in projects]

    # Mode selection: Switch/View, Create New, Edit Active
    tab1, tab2, tab3 = st.tabs(["Select & Switch Project", "Create New Project", "Edit Plant Parameters"])

    current_id = active_project.get("id") if active_project else (projects[0]["id"] if projects else None)

    # 1. Select & Switch Project
    with tab1:
        col1, col2 = st.columns([1.2, 0.8])
        with col1:
            st.markdown("##### Existing Projects in Local Database")
            if not projects:
                st.info("No projects exist. Create one in the next tab.")
            else:
                proj_df = pd.DataFrame([
                    {
                        "ID": p["id"],
                        "Name": p["name"],
                        "Location": p.get("location", ""),
                        "Head (m)": p.get("gross_head_m", 0.0),
                        "Design Flow (L/s)": p.get("design_flow_lps", 0.0),
                        "Updated": p.get("updated_at", "")[:10]
                    }
                    for p in projects
                ])
                st.dataframe(proj_df, use_container_width=True, hide_index=True)

                selected_name = st.selectbox(
                    "Select Active Project",
                    options=project_names,
                    index=project_names.index(active_project["name"]) if active_project and active_project["name"] in project_names else 0
                )

                if st.button("Set as Active Project", type="primary"):
                    new_proj = db.get_project_by_name(selected_name)
                    st.session_state["active_project"] = new_proj
                    st.rerun()

        with col2:
            st.markdown("##### Active Project Details")
            if active_project:
                st.write(f"**Name:** {active_project.get('name')}")
                st.write(f"**Location:** {active_project.get('location')}")
                st.write(f"**River:** {active_project.get('river_name')}")
                st.write(f"**Gross Head:** {active_project.get('gross_head_m')} m")
                st.write(f"**Design Flow:** {active_project.get('design_flow_lps')} L/s")
                st.write(f"**Penstock:** Ø {active_project.get('pipe_diameter_m')*1000:.0f} mm × {active_project.get('pipe_length_m')} m")
                st.write(f"**Turbine Type:** {active_project.get('turbine_type')}")
                st.write(f"**Description:** {active_project.get('description')}")

                # Delete Project with confirmation
                st.markdown("---")
                with st.expander("Delete This Project"):
                    st.warning(f"Permanently remove '{active_project.get('name')}' and all associated calculation history?")
                    confirm_delete = st.checkbox("Confirm Project Deletion")
                    if confirm_delete:
                        if st.button("Delete Project Now", type="secondary"):
                            db.delete_project(active_project["id"])
                            remaining = db.list_projects()
                            st.session_state["active_project"] = remaining[0] if remaining else None
                            st.success("Project deleted successfully.")
                            st.rerun()

    # 2. Create New Project
    with tab2:
        st.markdown("##### Create a New Hydropower Engineering Scheme")
        with st.form("create_project_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_name = st.text_input("Project Name *", value="", placeholder="e.g. Eagle Creek Micro-Hydro")
                new_loc = st.text_input("Site Location", value="", placeholder="e.g. Appenzell, Switzerland")
                new_river = st.text_input("River / Creek Name", value="", placeholder="e.g. Sitter River")
                new_desc = st.text_area("Project Description", value="", placeholder="Run-of-river scheme with diversion canal...")
            with c2:
                new_head = st.number_input("Gross Head (m) *", min_value=0.5, max_value=2500.0, value=35.0, step=0.5)
                new_flow = st.number_input("Design Flow (L/s) *", min_value=1.0, max_value=500000.0, value=800.0, step=10.0)
                new_eff = st.number_input("Design Efficiency (%)", min_value=10.0, max_value=98.0, value=82.0, step=0.5) / 100.0
                new_diam = st.number_input("Penstock Internal Diameter (m)", min_value=0.05, max_value=12.0, value=0.45, step=0.05)
                new_len = st.number_input("Penstock Length (m)", min_value=1.0, max_value=25000.0, value=120.0, step=5.0)

            submitted = st.form_submit_button("Save & Create Project", type="primary")
            if submitted:
                if not new_name.strip():
                    st.error("Project Name is required.")
                else:
                    try:
                        pid = db.create_project(
                            name=new_name.strip(),
                            location=new_loc.strip(),
                            river_name=new_river.strip(),
                            description=new_desc.strip(),
                            gross_head_m=new_head,
                            design_flow_lps=new_flow,
                            efficiency=new_eff,
                            pipe_diameter_m=new_diam,
                            pipe_length_m=new_len,
                        )
                        new_proj = db.get_project(pid)
                        st.session_state["active_project"] = new_proj
                        st.success(f"Project '{new_name}' created and set as active!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating project: {e}")

    # 3. Edit Active Project Parameters
    with tab3:
        if not active_project:
            st.info("Select a project first.")
        else:
            st.markdown(f"##### Edit Parameters: {active_project.get('name')}")
            with st.form("edit_project_form"):
                e1, e2 = st.columns(2)
                with e1:
                    e_name = st.text_input("Project Name", value=active_project.get("name", ""))
                    e_loc = st.text_input("Location", value=active_project.get("location", ""))
                    e_river = st.text_input("River / Waterway", value=active_project.get("river_name", ""))
                    e_desc = st.text_area("Description", value=active_project.get("description", ""))
                with e2:
                    e_head = st.number_input("Gross Head (m)", min_value=0.5, max_value=2500.0, value=float(active_project.get("gross_head_m", 25.0)), step=0.5)
                    e_flow = st.number_input("Design Flow (L/s)", min_value=1.0, max_value=500000.0, value=float(active_project.get("design_flow_lps", 1000.0)), step=10.0)
                    e_eff = st.number_input("Overall Efficiency (%)", min_value=10.0, max_value=98.0, value=float(active_project.get("efficiency", 0.82)*100.0), step=0.5) / 100.0
                    e_diam = st.number_input("Internal Pipe Diameter (m)", min_value=0.05, max_value=12.0, value=float(active_project.get("pipe_diameter_m", 0.50)), step=0.05)
                    e_len = st.number_input("Penstock Length (m)", min_value=1.0, max_value=25000.0, value=float(active_project.get("pipe_length_m", 150.0)), step=5.0)

                e_saved = st.form_submit_button("Update Project Details", type="primary")
                if e_saved:
                    success = db.update_project(
                        active_project["id"],
                        name=e_name.strip(),
                        location=e_loc.strip(),
                        river_name=e_river.strip(),
                        description=e_desc.strip(),
                        gross_head_m=e_head,
                        design_flow_lps=e_flow,
                        efficiency=e_eff,
                        pipe_diameter_m=e_diam,
                        pipe_length_m=e_len,
                    )
                    if success:
                        st.session_state["active_project"] = db.get_project(active_project["id"])
                        st.success("Project updated successfully.")
                        st.rerun()
                    else:
                        st.error("Failed to update project.")

    return st.session_state.get("active_project")
