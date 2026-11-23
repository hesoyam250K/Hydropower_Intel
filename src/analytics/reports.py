"""Local PDF engineering report generation and CSV data export engine.

Produces professional, publication-quality engineering reports locally using ReportLab.
Works completely offline without external APIs or cloud renderers.
"""

import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)

from src.engine.hydropower import HydropowerCalculationResult
from src.insights.interpretation import EngineeringObservation, generate_calculation_insights


def generate_pdf_report(
    calc: HydropowerCalculationResult,
    project_name: str = "Clearwater Run-of-River Hydro",
    location: str = "Cascade Range",
    river_name: str = "Clearwater Creek",
    engineer_name: str = "Civil / Hydro Systems Engineer",
    custom_notes: str = "",
    hydrothermal_res: Optional[Any] = None,
    structural_res: Optional[Any] = None
) -> bytes:
    """Generates a complete, multi-section engineering PDF report in memory."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom Engineering Report Typography
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#2563EB"),
        spaceAfter=15,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=14,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )

    code_style = ParagraphStyle(
        "FormulaCode",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
        backColor=colors.HexColor("#F1F5F9"),
        borderPadding=6,
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("HYDROPOWER INTELLIGENCE", subtitle_style))
    story.append(Paragraph(f"Hydraulic & Electrical Engineering Report: {project_name}", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2563EB"), spaceAfter=12))

    # 2. Metadata Box
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    meta_data = [
        [
            Paragraph(f"<b>Project:</b> {project_name}", body_style),
            Paragraph(f"<b>Date Generated:</b> {now_str}", body_style),
        ],
        [
            Paragraph(f"<b>Location:</b> {location}", body_style),
            Paragraph(f"<b>River / Waterway:</b> {river_name}", body_style),
        ],
        [
            Paragraph(f"<b>Prepared By:</b> {engineer_name}", body_style),
            Paragraph(f"<b>Application:</b> HydroPower Intelligence v1.0", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Executive Engineering Summary
    story.append(Paragraph("1. Executive Summary & Design Performance", section_heading))
    summary_data = [
        ["Parameter", "Symbol / Formula", "Calculated Value", "Engineering Units"],
        ["Volumetric Discharge", "Q", f"{calc.flow_lps:,.1f} / {calc.flow_m3s:.4f}", "L/s | m³/s"],
        ["Gross Static Head", "H_gross", f"{calc.gross_head_m:.2f}", "m (metres vertical drop)"],
        ["Total Head Loss", "H_loss (hf + hm)", f"{calc.head_loss_m:.3f}", "m (hydraulic friction + minor)"],
        ["Effective Net Head", "H_net = H_gross - H_loss", f"{calc.net_head_m:.3f}", "m"],
        ["Water-to-Wire Efficiency", "η", f"{calc.efficiency*100:.1f}", "% (combined water-to-wire)"],
        ["Theoretical Hydraulic Power", "P_hyd = ρ·g·Q·H_net", f"{calc.hydraulic_power_kw:,.2f}", "kW"],
        ["Electrical Power Output", "P_elec = P_hyd · η", f"{calc.electrical_power_kw:,.2f}", "kW"],
        ["Daily Energy Generation", "E_daily = P_elec · 24h", f"{calc.daily_energy_kwh:,.1f}", "kWh / day"],
        ["Annual Energy Yield Forecast", "E_annual (CF = 85%)", f"{calc.annual_energy_mwh:,.1f}", "MWh / year"],
        ["Recommended Turbine Type", "Turbine Regime", calc.turbine_selection.primary_recommendation if calc.turbine_selection else "N/A", "Optimal runner family"],
    ]
    summary_table = Table(summary_data, colWidths=[150, 160, 110, 110])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # 4. Calculation Methodology and Substituted Formulas
    story.append(Paragraph("2. Governing Mathematical Equations & Substituted Steps", section_heading))
    for step in calc.substitution_steps:
        step_text = (
            f"<b>{step['step']}</b><br/>"
            f"Formula: <code>{step['formula']}</code><br/>"
            f"Substitution: <code>{step['substitution']}</code> → <b>Result: {step['result']}</b>"
        )
        story.append(Paragraph(step_text, body_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 8))

    # 5. Penstock & Hydraulic Loss Breakdown
    if calc.loss_breakdown:
        story.append(Paragraph("3. Hydraulic Penstock & Friction Loss Breakdown", section_heading))
        lb = calc.loss_breakdown
        loss_rows = [
            ["Item", "Specification / Formula", "Value", "Unit"],
            ["Calculation Method", "Hydraulic Formulation", lb.method, "Standard"],
            ["Pipe Length / Diameter", "L / D", f"{lb.pipe_length_m:.1f} / {lb.pipe_diameter_m:.3f}", "m"],
            ["Mean Flow Velocity", "v = 4Q / πD²", f"{lb.flow_velocity_mps:.3f}", "m/s"],
            ["Velocity Head", "v² / 2g", f"{lb.velocity_head_m:.4f}", "m"],
            ["Reynolds Number", "Re = v·D / ν", f"{lb.reynolds_number:,.0f}", f"Regime: {lb.flow_regime}"],
            ["Friction Factor", "f (Darcy)", f"{lb.friction_factor:.4f}" if lb.friction_factor > 0 else "N/A", "Dimensionless"],
            ["Penstock Pipe Friction Loss", "hf", f"{lb.friction_loss_m:.3f}", "m"],
            ["Fittings Minor Losses", "hm = ΣK · v²/2g", f"{lb.minor_losses_m:.3f}", "m"],
            ["Total Head Loss", "H_loss = hf + hm", f"{lb.total_head_loss_m:.3f}", "m"],
        ]
        loss_table = Table(loss_rows, colWidths=[150, 160, 110, 110])
        loss_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(loss_table)
        story.append(Spacer(1, 10))

    # 6. Hydrothermal Bridge & Conduit Assessment (If Enabled)
    if hydrothermal_res:
        story.append(Paragraph("4. Hydrothermal Conduit & Thermal Bridge Assessment", section_heading))
        th = hydrothermal_res
        st_data = structural_res
        th_rows = [
            ["Hydrothermal Parameter", "Governing Formula", "Value", "Unit"],
            ["Fluid Mass Flow Rate", "ṁ = ρ × Q", f"{th.mass_flow_rate_kg_s:,.1f}", "kg/s"],
            ["Inlet / Outlet Water Temp", "T_in / T_out", f"{th.inlet_temp_c:.1f} / {th.outlet_temp_c:.2f}", "°C"],
            ["Ambient Air Temperature", "T_ambient", f"{th.ambient_air_temp_c:.1f}", "°C"],
            ["Convective Heat Transfer", "Q_thermal = ṁ·cp·ΔT", f"{th.fluid_thermal_transfer_kw:,.1f}", "kW"],
            ["Conductive Bridge Loss", "Q_cond = U·A·ΔT", f"{th.thermal_bridge_loss_kw:,.2f}", "kW"],
            ["1D Fourier Conduction", "q = -k·∇T", f"{th.fourier_heat_flux_w_m2:.1f}", "W/m²"],
        ]
        if st_data:
            th_rows.extend([
                ["Linear Thermal Expansion", "ΔL = α·L₀·ΔT", f"{st_data.expansion_mm:+.2f}", "mm"],
                ["Restrained Thermal Stress", "σ = R·E·α·ΔT", f"{st_data.thermal_stress_mpa:+.2f}", "MPa"],
                ["Structural Utilization", "η = |σ| / σ_yield", f"{st_data.utilization_ratio_pct:.1f}%", f"Capacity: {st_data.allowable_strength_mpa:.0f} MPa"],
            ])
        th_table = Table(th_rows, colWidths=[150, 160, 110, 110])
        th_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#065F46")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(th_table)
        story.append(Spacer(1, 8))

    # 7. Rule-Based Engineering Insights & Recommendations
    story.append(Paragraph("5. Rule-Based Engineering Observations & Site Recommendations", section_heading))
    insights = generate_calculation_insights(calc)
    for obs in insights:
        color_hex = "#2563EB" if obs.level in ("INFO", "OPTIMIZATION") else "#D97706"
        card_content = [
            [Paragraph(f"<b>[{obs.category}] {obs.title}</b> ({obs.level})", ParagraphStyle("H", parent=body_style, fontName="Helvetica-Bold", textColor=colors.HexColor(color_hex)))],
            [Paragraph(f"<b>Observation:</b> {obs.observation}", body_style)],
            [Paragraph(f"<b>Recommendation:</b> {obs.recommendation}", body_style)],
            [Paragraph(f"<i>Principle: {obs.governing_principle}</i>", ParagraphStyle("P", parent=body_style, fontSize=7.5, textColor=colors.HexColor("#64748B")))],
        ]
        card_table = Table(card_content, colWidths=[520])
        card_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(color_hex)),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(card_table)
        story.append(Spacer(1, 6))

    # 7. Assumptions & Limitations Notice
    story.append(Spacer(1, 8))
    story.append(Paragraph("5. Engineering Assumptions & Limitations", section_heading))
    notes_text = (
        "• Fresh water density assumed at standard temperature (ρ = 1,000 kg/m³, g = 9.81 m/s²).<br/>"
        "• Head loss calculation assumes steady, fully developed 1D conduit flow.<br/>"
        "• Turbine selection represents preliminary screening based on net head, discharge, and specific speed. "
        "Final equipment procurement requires comprehensive flow duration curve integration, cavitation submergence tests, and vendor hill charts.<br/>"
        "• This computational model is an engineering sizing and investigation tool and does not replace site-specific geotechnical, environmental, and structural civil plant design."
    )
    story.append(Paragraph(notes_text, body_style))

    doc.build(story)
    return buffer.getvalue()


def export_calculation_to_csv(calc: HydropowerCalculationResult, project_name: str) -> str:
    """Exports a calculation record to formatted CSV string."""
    rows = [
        {"Parameter": "Project Name", "Value": project_name, "Unit": ""},
        {"Parameter": "Date", "Value": datetime.now().isoformat(), "Unit": ""},
        {"Parameter": "Flow Rate (L/s)", "Value": round(calc.flow_lps, 2), "Unit": "L/s"},
        {"Parameter": "Flow Rate (m³/s)", "Value": round(calc.flow_m3s, 4), "Unit": "m³/s"},
        {"Parameter": "Gross Head", "Value": round(calc.gross_head_m, 2), "Unit": "m"},
        {"Parameter": "Head Loss", "Value": round(calc.head_loss_m, 3), "Unit": "m"},
        {"Parameter": "Net Head", "Value": round(calc.net_head_m, 3), "Unit": "m"},
        {"Parameter": "Efficiency", "Value": round(calc.efficiency, 4), "Unit": "decimal"},
        {"Parameter": "Hydraulic Power", "Value": round(calc.hydraulic_power_kw, 2), "Unit": "kW"},
        {"Parameter": "Electrical Power", "Value": round(calc.electrical_power_kw, 2), "Unit": "kW"},
        {"Parameter": "Operating Duration", "Value": round(calc.operating_hours, 1), "Unit": "hours"},
        {"Parameter": "Calculated Energy", "Value": round(calc.energy_kwh, 2), "Unit": "kWh"},
        {"Parameter": "Daily Energy", "Value": round(calc.daily_energy_kwh, 2), "Unit": "kWh"},
        {"Parameter": "Annual Energy Forecast", "Value": round(calc.annual_energy_mwh, 2), "Unit": "MWh"},
        {"Parameter": "Recommended Turbine", "Value": calc.turbine_selection.primary_recommendation if calc.turbine_selection else "N/A", "Unit": ""},
    ]
    df = pd.DataFrame(rows)
    return df.to_csv(index=False)


def export_simulation_to_csv(sim: Any) -> str:
    """Exports time-series simulation results to CSV."""
    df = pd.DataFrame({
        "time_seconds": sim.time_s,
        "flow_m3s": sim.flow_m3s,
        "flow_lps": sim.flow_lps,
        "net_head_m": sim.net_head_m,
        "water_level_m": sim.water_level_m,
        "gate_opening_pct": sim.gate_position_pct,
        "speed_rpm": sim.speed_rpm,
        "frequency_hz": sim.frequency_hz,
        "mechanical_power_kw": sim.mechanical_power_kw,
        "electrical_power_kw": sim.electrical_power_kw,
        "penstock_friction_head_m": sim.friction_head_m,
    })
    return df.to_csv(index=False)


def export_hydrothermal_to_csv(
    th_res: Any,
    st_res: Optional[Any] = None,
    project_name: str = "Hydropower Project"
) -> str:
    """Exports coupled hydrothermal and structural results to formatted CSV."""
    rows = [
        {"Parameter": "Project Name", "Value": project_name, "Unit": ""},
        {"Parameter": "Date", "Value": datetime.now().isoformat(), "Unit": ""},
        {"Parameter": "Mass Flow Rate", "Value": round(th_res.mass_flow_rate_kg_s, 2), "Unit": "kg/s"},
        {"Parameter": "Volumetric Flow Rate", "Value": round(th_res.volumetric_flow_m3s, 4), "Unit": "m³/s"},
        {"Parameter": "Inlet Fluid Temperature", "Value": round(th_res.inlet_temp_c, 2), "Unit": "°C"},
        {"Parameter": "Outlet Fluid Temperature", "Value": round(th_res.outlet_temp_c, 2), "Unit": "°C"},
        {"Parameter": "Mean Fluid Temperature", "Value": round(th_res.mean_fluid_temp_c, 2), "Unit": "°C"},
        {"Parameter": "Ambient Air Temperature", "Value": round(th_res.ambient_air_temp_c, 2), "Unit": "°C"},
        {"Parameter": "Convective Fluid Thermal Transfer", "Value": round(th_res.fluid_thermal_transfer_kw, 2), "Unit": "kW"},
        {"Parameter": "Conductive Thermal Bridge Loss", "Value": round(th_res.thermal_bridge_loss_kw, 2), "Unit": "kW"},
        {"Parameter": "1D Fourier Heat Flux", "Value": round(th_res.fourier_heat_flux_w_m2, 2), "Unit": "W/m²"},
        {"Parameter": "Heat Transfer Mode", "Value": th_res.heat_transfer_mode, "Unit": ""},
    ]
    if st_res:
        rows.extend([
            {"Parameter": "Linear Thermal Expansion", "Value": round(st_res.expansion_mm, 2), "Unit": "mm"},
            {"Parameter": "Restrained Thermal Stress", "Value": round(st_res.thermal_stress_mpa, 2), "Unit": "MPa"},
            {"Parameter": "Restraint Factor R", "Value": round(st_res.restraint_factor, 2), "Unit": "fraction"},
            {"Parameter": "Structural Utilization", "Value": round(st_res.utilization_ratio_pct, 1), "Unit": "%"},
            {"Parameter": "Stress Nature", "Value": st_res.stress_nature, "Unit": ""},
        ])
    return pd.DataFrame(rows).to_csv(index=False)
