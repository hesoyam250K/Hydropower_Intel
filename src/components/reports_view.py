"""Reports and Data Exports interface for PDF and CSV generation."""

from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd

from src.database.storage import DatabaseManager
from src.engine.hydropower import calculate_comprehensive_hydropower
from src.analytics.reports import (
    generate_pdf_report,
    export_calculation_to_csv,
    export_simulation_to_csv,
    export_hydrothermal_to_csv,
)
from src.hydrothermal.heat_transfer import analyze_hydrothermal_system
from src.hydrothermal.structural import analyze_thermal_structural_behavior
from src.simulation.scenarios import run_dynamic_simulation, SimulationConfig


def render_reports_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the engineering reports and data exports workspace."""
    st.subheader("Reports & Data Exports")
    st.caption("Generate formal engineering PDF reports and export calculation/simulation datasets locally.")

    if not active_project:
        st.warning("Please select an active project in the Project Manager to generate reports.")
        return

    rep_tab1, rep_tab2, rep_tab3 = st.tabs(["PDF Engineering Report", "CSV Data Exports", "Historical Calculation Archives"])

    # 1. PDF Report Generation
    with rep_tab1:
        st.markdown("##### Generate Comprehensive PDF Engineering Report")
        st.write("Produces an offline PDF document including design tables, substituted formulas, friction loss breakdown, and rule-based diagnostic observations.")

        rc1, rc2 = st.columns(2)
        with rc1:
            rep_engineer = st.text_input("Lead Engineer / Analyst", value="Civil / Mechanical Hydro Engineer")
            rep_notes = st.text_area("Engineering Scope & Custom Notes", value="Preliminary hydraulic sizing and electromechanical equipment assessment.")
        with rc2:
            st.markdown("###### Report Options")
            st.checkbox("Include Darcy-Weisbach Penstock Breakdown", value=True)
            st.checkbox("Include Turbine Specific Speed & Regime Classification", value=True)
            st.checkbox("Include Automated Engineering Insights & Recommendations", value=True)
            inc_thermal = st.checkbox("Include Hydrothermal Bridge & Thermal Stress Section", value=True)

        # Build baseline calculation for report
        calc = calculate_comprehensive_hydropower(
            flow_lps=float(active_project.get("design_flow_lps", 1000.0)),
            gross_head_m=float(active_project.get("gross_head_m", 25.0)),
            loss_method="darcy_weisbach",
            pipe_diameter_m=float(active_project.get("pipe_diameter_m", 0.50)),
            pipe_length_m=float(active_project.get("pipe_length_m", 150.0)),
            roughness_mm=float(active_project.get("roughness_mm", 0.045)),
            efficiency=float(active_project.get("efficiency", 0.82)),
        )

        th_res = None
        st_res = None
        if inc_thermal:
            th_res = analyze_hydrothermal_system(
                flow_lps=calc.flow_lps,
                inlet_temp_c=12.0,
                ambient_air_temp_c=-5.0,
                u_value_w_m2k=4.5,
                heat_transfer_area_m2=180.0,
                wall_thickness_m=0.35,
            )
            st_res = analyze_thermal_structural_behavior(
                initial_length_m=60.0,
                structure_temp_c=th_res.mean_fluid_temp_c,
                datum_temp_c=15.0,
                restraint_factor=0.5
            )

        pdf_bytes = generate_pdf_report(
            calc=calc,
            project_name=active_project.get("name", "Hydropower Project"),
            location=active_project.get("location", "Civil Engineering Site"),
            river_name=active_project.get("river_name", "Waterway"),
            engineer_name=rep_engineer,
            custom_notes=rep_notes,
            hydrothermal_res=th_res,
            structural_res=st_res
        )

        st.markdown("---")
        st.download_button(
            label="📄 Generate & Download Official Engineering PDF Report",
            data=pdf_bytes,
            file_name=f"Report_{active_project.get('name', 'Hydro')}.pdf",
            mime="application/pdf",
            type="primary"
        )

    # 2. CSV Data Exports
    with rep_tab2:
        st.markdown("##### Export Datasets to CSV")
        st.caption("Download structured tabular data for further processing in Excel, GIS, or MATLAB.")

        exp_col1, exp_col2, exp_col3 = st.columns(3)
        with exp_col1:
            st.markdown("###### Design Calculation Summary")
            calc_csv = export_calculation_to_csv(calc, active_project.get("name", "Project"))
            st.download_button(
                label="📊 Export Design Calculation (CSV)",
                data=calc_csv,
                file_name=f"Design_Calc_{active_project.get('name', 'Hydro')}.csv",
                mime="text/csv"
            )

        with exp_col2:
            st.markdown("###### Transient Simulation Time-Series")
            sim_res = run_dynamic_simulation(
                config=SimulationConfig(duration_s=30.0, scenario_type="load_rejection", event_time_s=5.0)
            )
            sim_csv = export_simulation_to_csv(sim_res)
            st.download_button(
                label="📈 Export Simulation Series (CSV)",
                data=sim_csv,
                file_name=f"Simulation_TimeSeries_{active_project.get('name', 'Hydro')}.csv",
                mime="text/csv"
            )

        with exp_col3:
            st.markdown("###### Hydrothermal & Structural Data")
            if th_res is None:
                th_res = analyze_hydrothermal_system(
                    flow_lps=calc.flow_lps,
                    inlet_temp_c=12.0,
                    ambient_air_temp_c=-5.0,
                    u_value_w_m2k=4.5,
                    heat_transfer_area_m2=180.0,
                    wall_thickness_m=0.35,
                )
                st_res = analyze_thermal_structural_behavior(
                    initial_length_m=60.0,
                    structure_temp_c=th_res.mean_fluid_temp_c,
                    datum_temp_c=15.0,
                    restraint_factor=0.5
                )
            hydro_csv = export_hydrothermal_to_csv(th_res, st_res, active_project.get("name", "Project"))
            st.download_button(
                label="🌡️ Export Hydrothermal Data (CSV)",
                data=hydro_csv,
                file_name=f"Hydrothermal_{active_project.get('name', 'Hydro')}.csv",
                mime="text/csv"
            )

    # 3. Historical Calculation Archives
    with rep_tab3:
        st.markdown("##### Saved Calculation History for Active Project")
        history = db.list_calculations(project_id=active_project.get("id"))
        if not history:
            st.info("No saved calculation records found in local SQLite database for this project.")
        else:
            hist_rows = []
            for h in history:
                hist_rows.append({
                    "ID": h["id"],
                    "Calculation Name": h.get("name", "Unnamed"),
                    "Flow (L/s)": h["inputs"].get("flow_lps", "N/A"),
                    "Gross Head (m)": h["inputs"].get("gross_head_m", "N/A"),
                    "Power (kW)": h["results"].get("electrical_power_kw", "N/A"),
                    "Net Head (m)": h["results"].get("net_head_m", "N/A"),
                    "Date": h.get("created_at", "")[:19].replace("T", " ")
                })
            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
