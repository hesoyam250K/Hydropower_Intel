"""Design Import Centre: CAD/BIM File Ingestion & Interoperability View."""

import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st

from src.database.storage import DatabaseManager
from src.cad.importer import CADImporter, ImportedModelResult
from src.cad.connectors import AutodeskAPSConnector, BentleyITwinConnector, HECRASConnector


def render_design_import_tab(db: DatabaseManager, active_project: Optional[Dict[str, Any]]) -> None:
    """Renders the comprehensive CAD/BIM Design Import Centre."""
    st.subheader("Design Import Centre")
    st.caption("Import, inspect, and convert civil, structural, and mechanical engineering designs (IFC 4.3, LandXML, STEP, STL, OBJ, GLB, GeoJSON).")

    p_id = active_project.get("id") if active_project else None
    p_name = active_project.get("name", "Default Project") if active_project else "Default Project"

    importer = CADImporter()

    tab_upload, tab_library, tab_connectors, tab_hecras = st.tabs([
        "1. File Ingestion & Conversion",
        "2. Imported Model Library",
        "3. Cloud CAD Pathways (Autodesk / Bentley)",
        "4. Hydraulic Model Ingest (HEC-RAS)"
    ])

    # =========================================================================
    # TAB 1: FILE INGESTION & CONVERSION
    # =========================================================================
    with tab_upload:
        st.markdown("##### Upload Engineering Design File")
        st.write(f"Target Project: **{p_name}**")

        col_up1, col_up2 = st.columns([1.5, 1.0])

        with col_up1:
            uploaded_file = st.file_uploader(
                "Choose Engineering CAD / BIM / GIS / Data File",
                type=[
                    "dwg", "dxf", "dgn", "dwf", "dwt", "dws",
                    "step", "stp", "iges", "igs", "stl", "obj", "3ds", "ply", "fbx", "glb", "gltf", "dae", "3mf",
                    "ifc", "ifc4", "ifcxml", "ifczip", "landxml", "xml",
                    "shp", "geojson", "json", "kml", "kmz", "gml", "gpkg", "tif", "tiff",
                    "csv", "xlsx", "xls", "yaml", "yml", "vtk", "vtu", "vtp", "msh"
                ],
                help="Comprehensive engineering format support across CAD, BIM, GIS, 3D Solids, and Simulation Data."
            )

            model_custom_name = st.text_input(
                "Model Asset Name",
                value=os.path.splitext(uploaded_file.name)[0] if uploaded_file else "Hydropower_Design_Model"
            )

        with col_up2:
            dwg_conv = importer._dwg_converter_path
            dwg_status = f"<span style='color: #34D399;'>Active ({dwg_conv.split(':')[0]})</span>" if dwg_conv else "<span style='color: #F59E0B;'>DXF Recommended (No ODA found)</span>"

            st.markdown(
                f"""
                <div style="background: #1E293B; border-left: 3px solid #00ffff; padding: 10px 14px; border-radius: 4px; font-size: 11px;">
                    <b style="color: #00ffff;">Engineering Format Pathways:</b><br/>
                    • <b>CAD & Drafting:</b> .dwg, .dxf, .dgn, .dwf [DWG: {dwg_status}]<br/>
                    • <b>3D Solids & Meshes:</b> .step, .iges, .stl, .obj, .ply, .3ds, .dae, .3mf, .glb<br/>
                    • <b>Civil & BIM:</b> .ifc (4.3/zip/xml), .landxml (TIN & penstocks)<br/>
                    • <b>GIS & Geospatial:</b> .geojson, .kml, .kmz, .gml, .shp<br/>
                    • <b>Simulation & Data:</b> .csv, .xlsx, .yaml, .vtk, .msh<br/>
                    <div style="margin-top: 5px; color: #94A3B8; font-size: 10px;">
                        All imported models are shared across <b>3D Lab (JARVIS 3D)</b> and <b>Hydrothermal & 3D Lab</b>.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        if uploaded_file is not None:
            if st.button("🚀 Ingest & Process Model Geometry", type="primary"):
                with st.spinner("Parsing engineering geometry, validating hierarchy, and normalising coordinates..."):
                    file_bytes = uploaded_file.getvalue()
                    res: ImportedModelResult = importer.import_file(
                        file_source=file_bytes,
                        filename=uploaded_file.name
                    )

                    if res.success:
                        st.success(f"✓ Successfully processed **{res.model_name}** ({res.format_type})")

                        # Save to models directory
                        out_glb_name = f"{res.model_name}_{p_id or 0}.glb"
                        out_glb_path = importer.output_dir / out_glb_name
                        if res.glb_bytes:
                            with open(out_glb_path, "wb") as f:
                                f.write(res.glb_bytes)

                        # Save to database
                        m_id = db.save_imported_model(
                            project_id=p_id,
                            name=model_custom_name,
                            format_type=res.format_type,
                            file_path=str(out_glb_path),
                            component_count=len(res.components),
                            vertex_count=res.total_vertices,
                            face_count=res.total_faces,
                            bounds=res.bounds,
                            metadata=res.metadata
                        )

                        if res.components:
                            db.save_model_components(m_id, res.components)

                        st.session_state["active_imported_model_id"] = m_id
                        st.session_state["active_imported_glb_bytes"] = res.glb_bytes

                        # Display Summary Cards
                        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                        sc1.metric("Format", res.format_type)
                        sc2.metric("Pipeline", res.metadata.get("import_method", "NATIVE_DIRECT"))
                        sc3.metric("Components", len(res.components))
                        sc4.metric("Vertices", f"{res.total_vertices:,}")
                        sc5.metric("Triangles", f"{res.total_faces:,}")

                        if res.warnings:
                            for w in res.warnings:
                                st.warning(f"⚠️ {w}")

                        if res.geographic_origin.get("shifted_to_local_origin"):
                            st.info(
                                f"🌐 **Coordinate Normalization Applied:** Origin shifted from "
                                f"E: {res.geographic_origin.get('origin_easting_x', 0):,.1f}m, "
                                f"N: {res.geographic_origin.get('origin_northing_y', 0):,.1f}m to (0, 0, 0) "
                                f"to prevent 32-bit WebGL floating point jitter."
                            )

                        with st.expander("Extracted Component Hierarchy & BIM Identifiers", expanded=True):
                            comp_table = []
                            for c in res.components[:30]:
                                comp_table.append({
                                    "Component ID": c.get("component_id"),
                                    "Name": c.get("name"),
                                    "Category": c.get("category"),
                                    "GlobalId": c.get("global_id", "-")
                                })
                            st.dataframe(comp_table, use_container_width=True)

                        st.success(
                            "✓ **Cross-Environment Availability:** This model is now ready in both **Digital Twin (JARVIS 3D)** "
                            "and **Hydrothermal & 3D Lab**!"
                        )
                    else:
                        st.error(f"Ingestion failed: {', '.join(res.errors)}")

    # =========================================================================
    # TAB 2: IMPORTED MODEL LIBRARY
    # =========================================================================
    with tab_library:
        st.markdown("##### Project Model Repository")
        models = db.list_imported_models(project_id=p_id)

        if not models:
            st.info("No imported CAD/BIM models found for this project. Upload a file above.")
        else:
            for m in models:
                with st.expander(f"📦 {m['name']} ({m['format']}) — {m.get('created_at', '')[:19]}", expanded=False):
                    m_cols = st.columns([2, 1, 1])
                    with m_cols[0]:
                        st.write(f"• **Format:** `{m['format']}`")
                        st.write(f"• **Sub-Components:** `{m['component_count']}`")
                        st.write(f"• **Vertices / Faces:** `{m['vertex_count']:,}` / `{m['face_count']:,}`")
                        st.write(f"• **Path:** `{m['file_path']}`")
                    with m_cols[1]:
                        if st.button("Set as Active (3D & Hydrothermal)", key=f"btn_activate_{m['id']}"):
                            st.session_state["active_imported_model_id"] = m["id"]
                            if os.path.exists(m["file_path"]):
                                with open(m["file_path"], "rb") as f:
                                    st.session_state["active_imported_glb_bytes"] = f.read()
                            st.success(f"Active model set to '{m['name']}' across 3D Lab and Hydrothermal Lab.")
                    with m_cols[2]:
                        if os.path.exists(m["file_path"]):
                            with open(m["file_path"], "rb") as f:
                                st.download_button(
                                    label="📥 Download GLB",
                                    data=f.read(),
                                    file_name=f"{m['name']}.glb",
                                    mime="model/gltf-binary",
                                    key=f"dl_{m['id']}"
                                )
                        if st.button("🗑 Delete Model", key=f"del_{m['id']}"):
                            db.delete_imported_model(m["id"])
                            st.rerun()

    # =========================================================================
    # TAB 3: PROPRIETARY CLOUD PATHWAYS
    # =========================================================================
    with tab_connectors:
        st.markdown("##### Proprietary CAD/BIM Cloud Adapters")
        st.caption("Optional cloud pathways for Autodesk Platform Services and Bentley iTwin Platform.")

        col_aps, col_itwin = st.columns(2)

        with col_aps:
            st.markdown("###### Autodesk Platform Services (APS / Forge)")
            aps = AutodeskAPSConnector()
            status_aps = aps.check_status()
            if status_aps.is_offline:
                st.warning("⚠️ **APS Connector Offline**")
                st.write(status_aps.status_message)
                st.caption("To enable direct cloud sync with Revit / Civil 3D, set `APS_CLIENT_ID` and `APS_CLIENT_SECRET` in environment variables or System Configuration.")
            else:
                st.success(f"✓ {status_aps.status_message}")

        with col_itwin:
            st.markdown("###### Bentley iTwin Platform (OpenBridge / OpenFlows)")
            itwin = BentleyITwinConnector()
            status_itwin = itwin.check_status()
            if status_itwin.is_offline:
                st.warning("⚠️ **iTwin Connector Offline**")
                st.write(status_itwin.status_message)
                st.caption("To enable direct cloud sync with OpenBridge or OpenFlows, set `ITWIN_CLIENT_ID` and `ITWIN_CLIENT_SECRET` in environment variables.")
            else:
                st.success(f"✓ {status_itwin.status_message}")

    # =========================================================================
    # TAB 4: HEC-RAS HYDRAULIC SIMULATION INGEST
    # =========================================================================
    with tab_hecras:
        st.markdown("##### US Army Corps HEC-RAS Hydraulic Engine Parser")
        st.caption("Extract river cross-sections, water surface profiles, and spillway gate hydrostatic pressures from HEC-RAS model outputs.")

        hec_text = st.text_area(
            "Paste HEC-RAS Simulation Output Report (.rep or .p01 text)",
            value="""HEC-RAS Plan: 100-Year Peak Flood Inflow
Geom: Clearwater Dam and Spillway
Cross Section 1024.5
W.S. Elev: 108.45 m
Vel Chnl: 3.42 m/s
Spillway Gate 02 Hydrostatic: 425.8 kPa
""",
            height=140
        )

        if st.button("Parse Hydraulic Model Output"):
            hec = HECRASConnector()
            parsed = hec.parse_report_file(hec_text)
            if parsed.get("success"):
                st.success(f"✓ Successfully extracted hydraulic profile for **{parsed['plan_name']}**")
                h1, h2, h3 = st.columns(3)
                h1.metric("Gate Hydrostatic Pressure", f"{parsed['gate_hydrostatic_pressure_kpa']:.1f} kPa")
                h2.metric("Channel Velocity", f"{parsed['mean_channel_velocity_mps']:.2f} m/s")
                h3.metric("Peak Water Surface Elev", f"{parsed['peak_water_surface_elev_m']:.2f} m")
                st.json(parsed["extracted_sensors"])
