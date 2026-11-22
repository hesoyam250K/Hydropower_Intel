"""Unit tests for input validation boundaries and warnings."""

from src.engine.validation import validate_hydropower_inputs


def test_validation_clean_inputs():
    """Verifies that standard valid inputs pass with no errors."""
    res = validate_hydropower_inputs(
        flow_lps=500.0,
        gross_head_m=35.0,
        head_loss_m=1.5,
        efficiency=0.82,
        hours=24.0,
        pipe_diameter_m=0.4,
        pipe_length_m=120.0,
        roughness_mm=0.045,
    )
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_validation_rejections():
    """Verifies that invalid physics inputs are flagged as errors."""
    # Negative values
    res = validate_hydropower_inputs(flow_lps=-5.0, gross_head_m=-10.0, efficiency=1.5)
    assert res.is_valid is False
    assert len(res.errors) >= 3

    # Head loss >= gross head
    res_hl = validate_hydropower_inputs(flow_lps=100.0, gross_head_m=10.0, head_loss_m=12.0)
    assert res_hl.is_valid is False
    assert any("exceeds gross head" in err for err in res_hl.errors)

    # Negative pipe dimensions
    res_pipe = validate_hydropower_inputs(pipe_diameter_m=-0.5, pipe_length_m=-100.0)
    assert res_pipe.is_valid is False
    assert any("pipe diameter" in err.lower() for err in res_pipe.errors)


def test_validation_warnings():
    """Verifies that engineering warning boundaries trigger helpful alerts without blocking."""
    # High head loss ratio (> 20%)
    res = validate_hydropower_inputs(flow_lps=500.0, gross_head_m=100.0, head_loss_m=25.0)
    assert res.is_valid is True
    assert res.has_warnings is True
    assert any("exceeds 20%" in w for w in res.warnings)
