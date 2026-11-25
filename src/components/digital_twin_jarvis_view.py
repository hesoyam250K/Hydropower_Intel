"""Digital Twin (JARVIS 3D) Workspace: Full-Screen Sci-Fi HUD, AR Viewport, and Simulation Binding."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import streamlit as st

from src.database.storage import DatabaseManager
from src.engine.shared_data import SharedEngineeringContext, build_shared_context_from_calc
from src.engine.hydropower import calculate_comprehensive_hydropower
from src.components.jarvis_viewer import render_jarvis_viewer
from src.components.three_viewer import render_peppers_ghost_hologram
from src.geometry.mesh_builder import PlantGeometryBuilder
from src.geometry.exporter import build_scene_and_export_glb
from src.diagnostics.engine import FaultEngine


def render_digital_twin_jarvis_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the dedicated JARVIS 3D Digital Twin and Holographic AR Environment."""
    st.subheader("Digital Twin — JARVIS 3D & Holographic AR")
    st.caption("Interactive 3D engineering digital twin with dynamic translucent HUD, voice/text commands, fault highlighting, and camera-based AR.")

    # Base values
    gross_head = float(active_project.get("gross_head_m", 25.0)) if active_project else 25.0
    design_flow_lps = float(active_project.get("design_flow_lps", 1000.0)) if active_project else 1000.0
    pipe_d = float(active_project.get("pipe_diameter_m", 0.50)) if active_project else 0.50
    pipe_l = float(active_project.get("pipe_length_m", 150.0)) if active_project else 150.0
    eff = float(active_project.get("efficiency", 0.82)) if active_project else 0.82
    p_id = active_project.get("id") if active_project else None

    # Calculate base context
    calc_base = calculate_comprehensive_hydropower(
        flow_lps=design_flow_lps,
        gross_head_m=gross_head,
        loss_method="darcy_weisbach",
        pipe_diameter_m=pipe_d,
        pipe_length_m=pipe_l,
        efficiency=eff
    )
    shared_ctx = build_shared_context_from_calc(calc=calc_base, project=active_project)

    # Share FaultEngine via session_state so faults injected in Fault Detection tab persist here
    if "fault_engine" not in st.session_state:
        st.session_state["fault_engine"] = FaultEngine(db_manager=db)
    fault_engine: FaultEngine = st.session_state["fault_engine"]

    # Sub-tabs
    tab_viewport, tab_peppers_ghost = st.tabs([
        "⚡ JARVIS 3D HUD & AR Viewport",
        "🌌 Pepper's Ghost 4-View Pyramid Hologram"
    ])

    with tab_viewport:
        # Top Controls Bar
        c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.0, 1.0])

        with c1:
            # Model Selection: Procedural vs Imported CAD
            imported_models = db.list_imported_models(project_id=p_id)
            model_choices = ["Standard Procedural (Hydropower + Bridge)"]
            model_map = {}
            active_m_id = st.session_state.get("active_imported_model_id")
            default_idx = 0
            for idx, m in enumerate(imported_models):
                label = f"CAD Asset: {m['name']} ({m['format']})"
                model_choices.append(label)
                model_map[label] = m
                if m["id"] == active_m_id:
                    default_idx = idx + 1

            selected_model_label = st.selectbox(
                "3D Model Source",
                options=model_choices,
                index=default_idx if default_idx < len(model_choices) else 0
            )

        with c2:
            data_source = st.selectbox(
                "Telemetry Data Binding",
                options=[
                    "Design Baseline Calculation",
                    "Live Telemetry Buffer",
                    "Simulation Lab Transient",
                    "Physical Turbine Demonstrator"
                ],
                index=0
            )

        with c3:
            vis_mode = st.selectbox(
                "Visualization Overlay",
                options=["FLOW", "THERMAL", "STRUCTURAL"],
                format_func=lambda m: {
                    "FLOW": "Water Flow (Velocity)",
                    "THERMAL": "Thermal Bridge (Heat Field)",
                    "STRUCTURAL": "Restrained Stress (MPa)"
                }[m],
                index=0
            )

        with c4:
            subsystem_filter = st.selectbox(
                "Subsystem Filter",
                options=["BOTH", "HYDROPOWER_ONLY", "BRIDGE_ONLY"],
                format_func=lambda s: {
                    "BOTH": "Complete Facility",
                    "HYDROPOWER_ONLY": "Hydropower Plant Only",
                    "BRIDGE_ONLY": "Hydrothermal Bridge Only"
                }[s],
                index=0
            )

        # Fault overlay controls
        fault_col_a, fault_col_b = st.columns([1, 4])
        with fault_col_a:
            if st.button("🔄 Refresh Fault Overlay", help="Streamlit doesn't auto-refresh between tabs. Click to pull latest active faults from the shared engine."):
                st.rerun()
        with fault_col_b:
            active_count = len(fault_engine.active_alerts)
            if active_count == 0:
                st.success("✓ **Fault Overlay:** 0 active faults — all systems nominal.")
            else:
                severity_counts = {}
                for a in fault_engine.active_alerts.values():
                    severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1
                badge = " | ".join(f"{v}× {k}" for k, v in severity_counts.items())
                st.warning(f"⚠ **Fault Overlay:** {active_count} active fault(s) loaded → {badge}")

        # Apply Live Telemetry if selected
        if data_source == "Live Telemetry Buffer" and "telemetry_buffer" in st.session_state and st.session_state["telemetry_buffer"]:
            latest = st.session_state["telemetry_buffer"][-1]
            shared_ctx.flow_lps = latest.get("flow_lps", shared_ctx.flow_lps)
            shared_ctx.net_head_m = latest.get("net_head_m", shared_ctx.net_head_m)
            shared_ctx.electrical_power_kw = latest.get("power_kw", shared_ctx.electrical_power_kw)
            shared_ctx.frequency_hz = latest.get("frequency_hz", shared_ctx.frequency_hz)
            shared_ctx.data_provenance = "LIVE_SCADA"

        elif data_source == "Physical Turbine Demonstrator" and "physical_turbine_packet" in st.session_state:
            tp = st.session_state["physical_turbine_packet"]
            shared_ctx.flow_lps = tp.flow_lps
            shared_ctx.net_head_m = tp.net_head_m
            shared_ctx.electrical_power_kw = tp.electrical_power_kw
            shared_ctx.runner_speed_rpm = tp.runner_rpm
            shared_ctx.frequency_hz = tp.frequency_hz
            shared_ctx.data_provenance = f"PHYSICAL_TURBINE_{tp.operating_mode}"

        # Determine GLB bytes
        custom_glb = None
        if selected_model_label != "Standard Procedural (Hydropower + Bridge)" and selected_model_label in model_map:
            target_m = model_map[selected_model_label]
            if os.path.exists(target_m["file_path"]):
                with open(target_m["file_path"], "rb") as f:
                    custom_glb = f.read()

        # Query active faults for 3D visual highlighting
        fault_payloads = fault_engine.get_3d_highlight_payloads()

        # Render the JARVIS 3D Viewport
        render_jarvis_viewer(
            context=shared_ctx,
            builder=PlantGeometryBuilder(
                gross_head_m=gross_head,
                pipe_diameter_m=pipe_d,
                include_bridge=(subsystem_filter != "HYDROPOWER_ONLY")
            ),
            custom_glb_bytes=custom_glb,
            mode=vis_mode,
            model_filter=subsystem_filter,
            fault_payloads=fault_payloads,
            height=720
        )

        st.caption("Navigation: Orbit: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll Wheel | Speech: Click 🎙 and speak commands.")

    with tab_peppers_ghost:
        st.markdown("##### Synchronized 4-View Pepper's Ghost Hologram")
        st.caption("Quad-quadrant spatial layout for inverted acrylic pyramid reflectors.")

        render_peppers_ghost_hologram(
            context=shared_ctx,
            builder=PlantGeometryBuilder(gross_head_m=gross_head, include_bridge=True),
            mode=vis_mode,
            height=720
        )
