"""Unit tests for sensitivity analytics, insights generation, and PDF reports."""

import pytest
from src.engine.hydropower import calculate_comprehensive_hydropower
from src.insights.interpretation import generate_calculation_insights
from src.analytics.performance import (
    sweep_flow_vs_power,
    sweep_head_vs_power,
    sweep_diameter_sensitivity,
    sweep_economic_tariff_sensitivity,
)
from src.analytics.reports import (
    generate_pdf_report,
    export_calculation_to_csv,
    export_hydrothermal_to_csv,
)
from src.hydrothermal.heat_transfer import analyze_hydrothermal_system
from src.hydrothermal.structural import analyze_thermal_structural_behavior


def test_insights_generation():
    """Verifies that engineering insights detect high friction and sizing issues."""
    # Calculation with very high head loss
    calc = calculate_comprehensive_hydropower(
        flow_lps=1000.0,
        gross_head_m=20.0,
        loss_method="manual",
        manual_head_loss_m=4.5,  # > 20% of gross head
        efficiency=0.75,
    )
    insights = generate_calculation_insights(calc)
    assert len(insights) >= 2
    assert any("Friction Losses" in obs.title for obs in insights)


def test_sensitivity_sweeps():
    """Verifies that parametric sweeps produce valid DataFrames."""
    df_flow = sweep_flow_vs_power(gross_head_m=30.0, min_flow_lps=100.0, max_flow_lps=1000.0, steps=10)
    assert len(df_flow) == 10
    assert "electrical_power_kw" in df_flow.columns
    assert df_flow["electrical_power_kw"].iloc[-1] > df_flow["electrical_power_kw"].iloc[0]

    df_diam = sweep_diameter_sensitivity(flow_m3s=0.5, gross_head_m=40.0, steps=5)
    assert len(df_diam) == 5
    # As diameter increases, friction loss decreases
    assert df_diam["friction_loss_m"].iloc[-1] < df_diam["friction_loss_m"].iloc[0]

    df_tariff = sweep_economic_tariff_sensitivity(annual_energy_mwh=1500.0)
    assert len(df_tariff) > 0


def test_pdf_report_generation():
    """Verifies local ReportLab PDF generation generates non-empty binary bytes."""
    calc = calculate_comprehensive_hydropower(
        flow_lps=1000.0,
        gross_head_m=20.0,
        loss_method="manual",
        manual_head_loss_m=2.0,
        efficiency=0.75,
    )
    pdf_bytes = generate_pdf_report(calc, project_name="Clearwater Test")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000  # Multi-kilobyte valid PDF
    assert pdf_bytes.startswith(b"%PDF-")  # Valid PDF signature


def test_csv_export():
    """Verifies CSV generation formatting."""
    calc = calculate_comprehensive_hydropower(flow_lps=500.0, gross_head_m=30.0)
    csv_str = export_calculation_to_csv(calc, "Test Project")
    assert "Flow Rate (L/s)" in csv_str
    assert "500.0" in csv_str


def test_hydrothermal_pdf_and_csv_reports():
    """Verifies that hydrothermal results integrate into PDF reports and CSV exports."""
    calc = calculate_comprehensive_hydropower(flow_lps=800.0, gross_head_m=25.0)
    th = analyze_hydrothermal_system(
        flow_lps=800.0,
        inlet_temp_c=12.0,
        ambient_air_temp_c=-4.0,
        u_value_w_m2k=4.5,
        heat_transfer_area_m2=150.0,
        wall_thickness_m=0.35
    )
    st_res = analyze_thermal_structural_behavior(
        initial_length_m=50.0,
        structure_temp_c=th.mean_fluid_temp_c,
        datum_temp_c=15.0,
        restraint_factor=0.5
    )

    # PDF with hydrothermal section
    pdf_bytes = generate_pdf_report(
        calc=calc,
        project_name="Bridge Hydro Plant",
        hydrothermal_res=th,
        structural_res=st_res
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 2000

    # Hydrothermal CSV
    csv_str = export_hydrothermal_to_csv(th, st_res, "Bridge Hydro Plant")
    assert "Mass Flow Rate" in csv_str
    assert "Restrained Thermal Stress" in csv_str
