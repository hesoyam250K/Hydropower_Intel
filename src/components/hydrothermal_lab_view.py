"""Hydrothermal & 3D Lab: Unified workspace combining Hydrothermal Analysis, 3D Engineering Viewer, and Hologram Display."""

import io
import os
from typing import Any, Dict, List, Optional
import numpy as np
import streamlit as st
import pandas as pd

from src.database.storage import DatabaseManager
from src.hydrothermal.materials import get_material, list_materials, MATERIAL_DATABASE, EngineeringMaterial
from src.hydrothermal.boundary_conditions import HydrothermalBoundaryConditions, SUPPORT_CONDITIONS
from src.hydrothermal.heat_transfer import analyze_hydrothermal_system, HydrothermalHeatTransferResult
from src.hydrothermal.structural import analyze_thermal_structural_behavior, ThermalStructuralResult
from src.hydrothermal.thermal_bridge import WallLayer, analyze_composite_thermal_bridge
from src.hydrothermal.validation import validate_hydrothermal_inputs
from src.engine.shared_data import SharedEngineeringContext, build_shared_context_from_calc
from src.engine.hydropower import calculate_comprehensive_hydropower
from src.components.three_viewer import render_threejs_viewer, render_peppers_ghost_hologram, render_jarvis_viewer
from src.geometry.mesh_builder import PlantGeometryBuilder
from src.geometry.exporter import build_scene_and_export_glb


def render_hydrothermal_3d_lab_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the comprehensive Hydrothermal & 3D Engineering Lab."""
    st.subheader("Hydrothermal & 3D Lab")
    st.caption("Coupled hydraulic, thermal-bridge, and structural stress analysis with interactive 3D WebGL and Pepper's Ghost holographic rendering.")

    # Base values from active project
    gross_head = float(active_project.get("gross_head_m", 25.0)) if active_project else 25.0
    design_flow_lps = float(active_project.get("design_flow_lps", 1000.0)) if active_project else 1000.0
    pipe_d = float(active_project.get("pipe_diameter_m", 0.50)) if active_project else 0.50
    pipe_l = float(active_project.get("pipe_length_m", 150.0)) if active_project else 150.0
    eff = float(active_project.get("efficiency", 0.82)) if active_project else 0.82

    # Internal sub-navigation tabs
    tab_thermal, tab_3d, tab_hologram = st.tabs([
        "A. Hydrothermal Analysis",
        "B. 3D Engineering Viewer",
        "C. Hologram Display"
    ])

    # Session state for shared hydrothermal settings
    if "hydrothermal_bc" not in st.session_state:
        st.session_state["hydrothermal_bc"] = HydrothermalBoundaryConditions(
            flow_lps=design_flow_lps,
            inlet_temp_c=12.0,
            ambient_air_temp_c=-5.0,
            u_value_w_m2k=4.5,
            bridge_length_m=60.0,
            heat_transfer_area_m2=180.0,
            wall_thickness_m=0.35,
            support_condition="semi_restrained",
            restraint_factor=0.5
        )
    if "hydrothermal_mat_key" not in st.session_state:
        st.session_state["hydrothermal_mat_key"] = "reinforced_concrete"

    # =========================================================================
    # WORKSPACE A: HYDROTHERMAL ANALYSIS
    # =========================================================================
    with tab_thermal:
        st.markdown("#### Coupled Hydrothermal Bridge & Conduit Analysis")
        st.caption("Investigate convective fluid thermal transport, conductive thermal bridge leakage, linear thermal expansion, and restrained structural stress.")

        with st.expander("1. Geometry, Materials & Structural Restraint", expanded=True):
            g_col1, g_col2, g_col3 = st.columns(3)

            with g_col1:
                st.markdown("###### Conduit & Bridge Geometry")
                b_len = st.number_input("Span / Conduit Length L₀ (m)", min_value=5.0, max_value=2000.0, value=st.session_state["hydrothermal_bc"].bridge_length_m, step=5.0)
                b_area = st.number_input("Exposed Heat Transfer Area A (m²)", min_value=1.0, max_value=50000.0, value=st.session_state["hydrothermal_bc"].heat_transfer_area_m2, step=10.0)
                b_thick = st.number_input("Conduit Wall Thickness t (m)", min_value=0.02, max_value=2.0, value=st.session_state["hydrothermal_bc"].wall_thickness_m, step=0.05)

            with g_col2:
                st.markdown("###### Material Selection & Thermal Properties")
                mat_options = list_materials()
                selected_mat_key = st.selectbox(
                    "Structural Material",
                    options=list(mat_options.keys()),
                    format_func=lambda k: mat_options[k],
                    index=list(mat_options.keys()).index(st.session_state["hydrothermal_mat_key"])
                )
                mat_obj = get_material(selected_mat_key)
                st.session_state["hydrothermal_mat_key"] = selected_mat_key

                st.write(f"• Thermal Conductivity k: `{mat_obj.thermal_conductivity_w_mk} W/m·K`")
                st.write(f"• Young's Modulus E: `{mat_obj.youngs_modulus_gpa} GPa` ({mat_obj.youngs_modulus_mpa:,.0f} MPa)")
                st.write(f"• Expansion Coeff α: `{mat_obj.thermal_expansion_micro:.1f} μm/m·K`")
                st.write(f"• Yield Strength σ_y: `{mat_obj.yield_strength_mpa} MPa`")

            with g_col3:
                st.markdown("###### Structural Support & Restraint")
                supp_choice = st.selectbox(
                    "Support Boundary Condition",
                    options=list(SUPPORT_CONDITIONS.keys()),
                    format_func=lambda k: SUPPORT_CONDITIONS[k][0],
                    index=1
                )
                default_r = SUPPORT_CONDITIONS[supp_choice][1]
                if default_r is not None:
                    restraint_val = default_r
                    st.info(f"Fixed Restraint Factor R = {restraint_val:.2f}")
                else:
                    restraint_val = st.slider("Custom Restraint Factor R", min_value=0.0, max_value=1.0, value=0.5, step=0.05)

                datum_temp = st.number_input("Stress-Free Construction Datum Temp (°C)", min_value=-20.0, max_value=40.0, value=15.0, step=1.0)

        with st.expander("2. Boundary Conditions & Environmental Thermal Fields", expanded=True):
            bc1, bc2, bc3 = st.columns(3)

            with bc1:
                st.markdown("###### Hydraulic Discharge")
                st.write(f"Shared Project Flow: `{design_flow_lps:.1f} L/s` ({design_flow_lps/1000:.3f} m³/s)")
                override_flow = st.checkbox("Override Flow Rate for Thermal Study", value=False)
                if override_flow:
                    study_flow = st.number_input("Study Discharge (L/s)", min_value=1.0, max_value=500000.0, value=design_flow_lps, step=50.0)
                else:
                    study_flow = design_flow_lps

            with bc2:
                st.markdown("###### Fluid Operating Temperatures")
                t_in = st.number_input("Inlet Fluid Temperature T_in (°C)", min_value=-5.0, max_value=80.0, value=st.session_state["hydrothermal_bc"].inlet_temp_c, step=0.5)
                auto_tout = st.checkbox("Auto-Calculate Outlet Temp from Energy Balance", value=True)
                if auto_tout:
                    t_out_val = None
                else:
                    t_out_val = st.number_input("Measured Outlet Fluid Temp T_out (°C)", min_value=-5.0, max_value=80.0, value=t_in - 0.25, step=0.1)

            with bc3:
                st.markdown("###### Ambient External Climate")
                t_amb_air = st.number_input("Ambient Air Temperature T_amb (°C)", min_value=-50.0, max_value=60.0, value=st.session_state["hydrothermal_bc"].ambient_air_temp_c, step=1.0)
                t_amb_riv = st.number_input("Ambient River / Ground Temperature (°C)", min_value=-5.0, max_value=35.0, value=8.0, step=0.5)
                u_val = st.number_input("Overall Heat Transfer Coeff U (W/m²·K)", min_value=0.1, max_value=50.0, value=st.session_state["hydrothermal_bc"].u_value_w_m2k, step=0.5)

        # Update Session State Boundary Conditions
        bc_current = HydrothermalBoundaryConditions(
            flow_lps=study_flow,
            inlet_temp_c=t_in,
            outlet_temp_c=t_out_val,
            ambient_air_temp_c=t_amb_air,
            ambient_river_temp_c=t_amb_riv,
            u_value_w_m2k=u_val,
            bridge_length_m=b_len,
            heat_transfer_area_m2=b_area,
            wall_thickness_m=b_thick,
            support_condition=supp_choice,
            restraint_factor=restraint_val,
            construction_datum_temp_c=datum_temp
        )
        st.session_state["hydrothermal_bc"] = bc_current

        # Validation
        val_res = validate_hydrothermal_inputs(bc_current, mat_obj)
        for w in val_res.warnings:
            st.warning(f"⚠️ {w}")
        if not val_res.is_valid:
            for err in val_res.errors:
                st.error(f"❌ {err}")
            return

        # Perform Analyses
        th_res: HydrothermalHeatTransferResult = analyze_hydrothermal_system(
            flow_lps=bc_current.flow_lps,
            inlet_temp_c=bc_current.inlet_temp_c,
            ambient_air_temp_c=bc_current.ambient_air_temp_c,
            u_value_w_m2k=bc_current.u_value_w_m2k,
            heat_transfer_area_m2=bc_current.heat_transfer_area_m2,
            wall_thickness_m=bc_current.wall_thickness_m,
            outlet_temp_c=bc_current.outlet_temp_c,
            material=mat_obj
        )

        st_res: ThermalStructuralResult = analyze_thermal_structural_behavior(
            initial_length_m=bc_current.bridge_length_m,
            structure_temp_c=th_res.mean_fluid_temp_c,
            datum_temp_c=bc_current.construction_datum_temp_c,
            restraint_factor=bc_current.restraint_factor,
            material=mat_obj
        )

        # 3. Analysis Results Metrics
        st.markdown("---")
        st.markdown("##### 3. Analysis Results & Performance Indicators")
        r1, r2, r3, r4, r5 = st.columns(5)
        with r1:
            st.metric("Fluid Mass Flow", f"{th_res.mass_flow_rate_kg_s:,.1f} kg/s", delta=f"{th_res.volumetric_flow_m3s:.3f} m³/s")
        with r2:
            st.metric("Mean Fluid Temp", f"{th_res.mean_fluid_temp_c:.2f} °C", delta=f"In: {th_res.inlet_temp_c:.1f}°C | Out: {th_res.outlet_temp_c:.2f}°C")
        with r3:
            st.metric("Fluid Heat Transfer", f"{th_res.fluid_thermal_transfer_kw:,.1f} kW", delta=f"{th_res.heat_transfer_mode.split()[0]}")
        with r4:
            st.metric("Conductive Bridge Loss", f"{th_res.thermal_bridge_loss_kw:,.2f} kW", delta=f"U = {bc_current.u_value_w_m2k} W/m²·K")
        with r5:
            st.metric("Thermal Stress σ", f"{st_res.thermal_stress_mpa:+.2f} MPa", delta=f"Exp: {st_res.expansion_mm:+.2f} mm", delta_color="inverse" if abs(st_res.thermal_stress_mpa) > 15 else "normal")

        # Step-by-Step Mathematical Formulations
        st.markdown("---")
        f_col1, f_col2 = st.columns(2)

        with f_col1:
            st.markdown("###### Convective & Conductive Governing Equations")
            for step in th_res.formula_substitutions:
                st.markdown(
                    f"""
                    <div class="formula-box">
                        <span style="color: #38BDF8; font-weight: bold;">{step['step']}</span><br/>
                        <span style="color: #94A3B8;">Formula:</span> <code>{step['formula']}</code><br/>
                        <span style="color: #94A3B8;">Substituted:</span> {step['substitution']} &rarr; <b>{step['result']}</b>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with f_col2:
            st.markdown("###### Thermal Expansion & Structural Stress Formulations")
            for step in st_res.formula_substitutions:
                st.markdown(
                    f"""
                    <div class="formula-box">
                        <span style="color: #10B981; font-weight: bold;">{step['step']}</span><br/>
                        <span style="color: #94A3B8;">Formula:</span> <code>{step['formula']}</code><br/>
                        <span style="color: #94A3B8;">Substituted:</span> {step['substitution']} &rarr; <b>{step['result']}</b>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            st.caption(f"<i>{st_res.engineering_qualification}</i>", unsafe_allow_html=True)

        # 4. Engineering Interpretation & Diagnostic Observations
        st.markdown("---")
        st.markdown("##### 4. Engineering Observations & Diagnostic Recommendations")

        # Evaluate risk cards
        if abs(st_res.expansion_mm) > 25.0:
            st.warning(f"⚠️ **High Thermal Movement**: Expected span expansion/contraction is {st_res.expansion_mm:+.1f} mm. Ensure modular finger joints provide ≥ ±{abs(st_res.expansion_mm)*1.5:.0f} mm movement capacity.")
        else:
            st.success(f"✓ **Thermal Movement Managed**: {st_res.expansion_mm:+.1f} mm expansion is within standard elastomeric bridge bearing travel.")

        if st_res.utilization_ratio_pct > 50.0:
            st.error(f"🚨 **High Restrained Stress**: Thermal stress reaches {st_res.thermal_stress_mpa:+.1f} MPa ({st_res.utilization_ratio_pct:.0f}% of allowable). Expansion bearings or sliding saddles required to prevent concrete cracking.")
        else:
            st.success(f"✓ **Structural Thermal Stress Nominal**: {st_res.thermal_stress_mpa:+.1f} MPa ({st_res.utilization_ratio_pct:.1f}% utilization).")

        if th_res.thermal_bridge_loss_kw > 20.0:
            st.warning(f"⚠️ **Elevated Thermal Loss**: Conductive loss through exposed conduit surfaces is {th_res.thermal_bridge_loss_kw:.1f} kW. Consider rigid polyurethane or aerogel insulation cladding.")

    # =========================================================================
    # WORKSPACE B: 3D ENGINEERING VIEWER
    # =========================================================================
    with tab_3d:
        st.markdown("#### Interactive 3D Engineering Model")
        st.caption("GPU-accelerated WebGL digital twin containing the complete hydropower plant and hydrothermal bridge conduit.")

        # Build active SharedEngineeringContext
        calc_base = calculate_comprehensive_hydropower(
            flow_lps=design_flow_lps,
            gross_head_m=gross_head,
            loss_method="darcy_weisbach",
            pipe_diameter_m=pipe_d,
            pipe_length_m=pipe_l,
            efficiency=eff
        )
        shared_ctx = build_shared_context_from_calc(
            calc=calc_base,
            project=active_project,
            thermal_res=th_res if 'th_res' in locals() else None,
            struct_res=st_res if 'st_res' in locals() else None
        )

        # -------------------------------------------------------------
        # Live Telemetry & Simulation Playback Binding Controls
        # -------------------------------------------------------------
        with st.expander("Telemetry & Simulation Playback Control Panel", expanded=False):
            pb_mode = st.radio(
                "3D Scene Data Source",
                options=[
                    "Design Calculation Baseline",
                    "Simulation Lab Transient Playback",
                    "Live SCADA Telemetry Stream"
                ],
                horizontal=True
            )

            if pb_mode == "Simulation Lab Transient Playback":
                sim_records = db.list_simulations(project_id=active_project.get("id") if active_project else None)
                if not sim_records:
                    st.info("No recorded simulations found. Run a simulation in the Simulation Lab first, or use a default scenario below:")
                
                # Transient scenario playback selector
                playback_scenario = st.selectbox(
                    "Select Playback Transient Run",
                    options=["load_rejection", "load_acceptance", "rapid_gate_closure", "steady_state"],
                    format_func=lambda s: {
                        "load_rejection": "Sudden Load Rejection (Grid Trip)",
                        "load_acceptance": "Load Acceptance (+50% Step Increase)",
                        "rapid_gate_closure": "Rapid Emergency Gate Closure (Surge)",
                        "steady_state": "Steady-State Baseline",
                    }[s]
                )
                from src.simulation.scenarios import run_dynamic_simulation, SimulationConfig
                sim_res_playback = run_dynamic_simulation(
                    config=SimulationConfig(duration_s=30.0, scenario_type=playback_scenario, event_time_s=8.0)
                )

                pb_cols = st.columns([2, 1, 1])
                with pb_cols[0]:
                    max_t = float(sim_res_playback.time_s[-1])
                    selected_t = st.slider("Timeline Scrubber (seconds)", min_value=0.0, max_value=max_t, value=8.5, step=0.1)
                with pb_cols[1]:
                    pb_speed = st.selectbox("Playback Speed", options=["0.5x", "1.0x", "2.0x", "5.0x"], index=1)
                with pb_cols[2]:
                    st.write("**Playback State:**")
                    st.markdown("<span class='badge badge-simulated'>SIMULATION REPLAY ACTIVE</span>", unsafe_allow_html=True)

                # Interpolate simulation state at selected time
                t_idx = int(np.searchsorted(sim_res_playback.time_s, selected_t))
                t_idx = min(len(sim_res_playback.time_s) - 1, max(0, t_idx))

                shared_ctx.simulation_time_s = float(selected_t)
                shared_ctx.flow_m3s = float(sim_res_playback.flow_m3s[t_idx])
                shared_ctx.flow_lps = float(sim_res_playback.flow_lps[t_idx])
                shared_ctx.net_head_m = float(sim_res_playback.net_head_m[t_idx])
                shared_ctx.electrical_power_kw = float(sim_res_playback.electrical_power_kw[t_idx])
                shared_ctx.runner_speed_rpm = float(sim_res_playback.speed_rpm[t_idx])
                shared_ctx.frequency_hz = float(sim_res_playback.frequency_hz[t_idx])
                shared_ctx.gate_position_pct = float(sim_res_playback.gate_position_pct[t_idx])
                area = np.pi * (pipe_d ** 2) / 4.0
                shared_ctx.water_velocity_mps = shared_ctx.flow_m3s / max(0.01, area)
                shared_ctx.data_provenance = "SIMULATION_DYNAMIC"

                st.caption(
                    f"Replaying t = {selected_t:.1f}s | Flow: {shared_ctx.flow_lps:.1f} L/s | "
                    f"Net Head: {shared_ctx.net_head_m:.1f} m | Power: {shared_ctx.electrical_power_kw:.1f} kW | "
                    f"Speed: {shared_ctx.runner_speed_rpm:.0f} RPM"
                )

            elif pb_mode == "Live SCADA Telemetry Stream":
                if "telemetry_buffer" in st.session_state and st.session_state["telemetry_buffer"]:
                    latest_telem = st.session_state["telemetry_buffer"][-1]
                    shared_ctx.flow_lps = latest_telem.get("flow_lps", shared_ctx.flow_lps)
                    shared_ctx.flow_m3s = shared_ctx.flow_lps / 1000.0
                    shared_ctx.net_head_m = latest_telem.get("net_head_m", shared_ctx.net_head_m)
                    shared_ctx.electrical_power_kw = latest_telem.get("power_kw", shared_ctx.electrical_power_kw)
                    shared_ctx.frequency_hz = latest_telem.get("frequency_hz", shared_ctx.frequency_hz)
                    shared_ctx.data_provenance = "LIVE_SCADA_" + latest_telem.get("source", "SIMULATED")

                    st.markdown(
                        f"""
                        <div style="background: #1E293B; border-left: 3px solid #10B981; padding: 6px 12px; border-radius: 4px; font-size: 11px;">
                            <span class="badge badge-normal">LIVE TELEMETRY BINDING</span>
                            <span style="color: #CBD5E1; margin-left: 8px;">
                                Streaming Active Power: <b>{shared_ctx.electrical_power_kw:.1f} kW</b> | Flow: <b>{shared_ctx.flow_lps:.1f} L/s</b> | Frequency: <b>{shared_ctx.frequency_hz:.2f} Hz</b>
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.info("No active telemetry stream in buffer. Start the stream in Live Telemetry.")

        v_ctrl1, v_ctrl2, v_ctrl3 = st.columns(3)
        with v_ctrl1:
            vis_mode = st.selectbox(
                "Engineering Visualization Overlay",
                options=["FLOW", "THERMAL", "STRUCTURAL"],
                format_func=lambda m: {
                    "FLOW": "Flow Mode (Streamlines, Velocity Field)",
                    "THERMAL": "Thermal Mode (Temperature Field, Heat Bridge)",
                    "STRUCTURAL": "Structural Mode (Thermal Stress, Expansion)"
                }[m],
                index=0
            )
        with v_ctrl2:
            model_scope = st.selectbox(
                "Subsystem Display Filter",
                options=["BOTH", "HYDROPOWER_ONLY", "BRIDGE_ONLY"],
                format_func=lambda s: {
                    "BOTH": "Complete Facility (Hydropower + Hydrothermal Bridge)",
                    "HYDROPOWER_ONLY": "Hydropower Installation Only",
                    "BRIDGE_ONLY": "Hydrothermal Bridge & Conduit Only"
                }[s],
                index=0
            )
        with v_ctrl3:
            st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
            # Export GLB / STL buttons
            glb_data = build_scene_and_export_glb(
                builder=PlantGeometryBuilder(gross_head_m=gross_head, pipe_diameter_m=pipe_d, include_bridge=(model_scope != "HYDROPOWER_ONLY")),
                context=shared_ctx,
                mode=vis_mode
            )
            st.download_button(
                label="📦 Export 3D Model (GLB)",
                data=glb_data,
                file_name=f"Plant_Model_{vis_mode}.glb",
                mime="model/gltf-binary"
            )

        viewer_style = st.radio(
            "Viewport Presentation Engine",
            options=["Standard Engineering View", "JARVIS 3D HUD & Holographic AR"],
            horizontal=True,
            index=0
        )

        # Render Selected Interactive Component
        if viewer_style == "JARVIS 3D HUD & Holographic AR":
            render_jarvis_viewer(
                context=shared_ctx,
                builder=PlantGeometryBuilder(gross_head_m=gross_head, pipe_diameter_m=pipe_d, include_bridge=(model_scope != "HYDROPOWER_ONLY")),
                mode=vis_mode,
                model_filter=model_scope,
                height=700
            )
        else:
            render_threejs_viewer(
                context=shared_ctx,
                builder=PlantGeometryBuilder(gross_head_m=gross_head, pipe_diameter_m=pipe_d, include_bridge=(model_scope != "HYDROPOWER_ONLY")),
                mode=vis_mode,
                model_filter=model_scope,
                height=660
            )

        st.caption("Navigation: Left Click + Drag to rotate | Right Click + Drag to pan | Mouse Wheel to zoom | Click components to inspect.")

    # =========================================================================
    # WORKSPACE C: HOLOGRAM DISPLAY
    # =========================================================================
    with tab_hologram:
        st.markdown("#### Pepper's Ghost 4-View Optical Hologram Display")
        st.caption("Full four-quadrant synchronized spatial projection for physical 4-sided acrylic or glass pyramid reflectors.")

        holo1, holo2 = st.columns([1.2, 0.8])
        with holo1:
            holo_mode = st.radio(
                "Hologram Visualization Overlay",
                options=["FLOW", "THERMAL", "STRUCTURAL"],
                horizontal=True
            )
        with holo2:
            st.info("💡 Position your 4-sided transparent acrylic pyramid inverted over the center target. Darken room lighting for optimal contrast.")

        # Render Pepper's Ghost Hologram Layout
        render_peppers_ghost_hologram(
            context=shared_ctx,
            builder=PlantGeometryBuilder(gross_head_m=gross_head, include_bridge=True),
            mode=holo_mode,
            height=720
        )

        with st.expander("DIY Pepper's Ghost Physical Setup & Optical Calibration Guide"):
            st.markdown(
                """
                **How to View the 3D Hologram:**
                1. **Fabricate a 4-Sided Pyramid**: Cut 4 congruent isosceles trapezoids from transparent rigid plastic (e.g., CD jewel case, acrylic, or polycarbonate sheet):
                   - Base width: 6.0 cm
                   - Top width: 1.0 cm
                   - Slant height: 3.5 cm
                2. **Assemble**: Tape the 4 edges together into a hollow truncated pyramid.
                3. **Placement**: Invert the pyramid with its small 1.0 cm opening resting flat over the central crosshair marker on your monitor or tablet.
                4. **Observation**: View horizontally through the sloping reflective walls. The 4 synchronized orthogonal views reflect into your line of sight, creating an optical floating 3D hologram in the center of the pyramid!
                """
            )
