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
)


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
