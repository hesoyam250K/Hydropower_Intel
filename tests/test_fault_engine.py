"""Unit tests for Digital Twin Fault Detection & Diagnostics Engine."""

import os
import tempfile
import pytest

from src.database.storage import DatabaseManager
from src.cad.sensor_mesh_mapper import SensorMeshMapper
from src.diagnostics.engine import FaultEngine, FaultSeverity, FaultType


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    yield db
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


@pytest.fixture
def fault_engine(temp_db):
    mapper = SensorMeshMapper()
    return FaultEngine(db_manager=temp_db, mesh_mapper=mapper)


def test_level1_normal_reading(fault_engine):
    """Verifies that normal sensor measurements generate no fault alerts."""
    alert = fault_engine.evaluate_sensor_reading(
        sensor_id="SCADA_TURB1_VIB_X",
        value=2.1,  # Below warning threshold (4.5)
        is_simulated=False
    )
    assert alert is None
    assert len(fault_engine.active_alerts) == 0


def test_level1_warning_and_critical_thresholds(fault_engine):
    """Verifies Level 1 rule-based warning and critical breaches."""
    # Warning breach
    alert_warn = fault_engine.evaluate_sensor_reading(
        sensor_id="SCADA_TURB1_VIB_X",
        value=5.8,  # Between 4.5 and 8.5
        is_simulated=False
    )
    assert alert_warn is not None
    assert alert_warn.severity == FaultSeverity.WARNING.value
    assert alert_warn.fault_type == FaultType.DETECTED.value
    assert alert_warn.component_id == "turbine_runner"
    assert "ISO 10816" in alert_warn.diagnostics.summary or "vibration" in alert_warn.message.lower()

    # Critical breach upgrade
    alert_crit = fault_engine.evaluate_sensor_reading(
        sensor_id="SCADA_TURB1_VIB_X",
        value=9.2,  # > 8.5
        is_simulated=False
    )
    assert alert_crit is not None
    assert alert_crit.severity == FaultSeverity.CRITICAL.value
    assert len(alert_crit.diagnostics.inspection_steps) >= 3


def test_simulated_fault_distinction_and_clearing(fault_engine):
    """Verifies simulated faults are labelled and can be bulk cleared."""
    sim_alerts = fault_engine.inject_simulated_fault("gate_pressure_surge")
    assert len(sim_alerts) == 1
    assert sim_alerts[0].is_simulated is True
    assert sim_alerts[0].fault_type == FaultType.SIMULATED.value
    assert "[SIMULATED]" in sim_alerts[0].message

    # Verify 3D highlight payload
    payloads = fault_engine.get_3d_highlight_payloads()
    assert len(payloads) == 1
    assert payloads[0]["color_hex"] == "#ff2244"
    assert payloads[0]["component_id"] == "intake_gate"

    # Reset demonstration
    cleared_count = fault_engine.clear_all_simulated_faults()
    assert cleared_count == 1
    assert len(fault_engine.active_alerts) == 0


def test_level2_statistical_anomaly_detection(fault_engine):
    """Verifies Z-score statistical outlier detection on steady baseline."""
    # Feed steady baseline
    for _ in range(25):
        fault_engine.evaluate_sensor_reading("IOT_DAM_CRACK_09", 0.50)

    # Sudden anomaly spike that doesn't breach the hard threshold of 1.2
    anomaly_alert = fault_engine.evaluate_sensor_reading("IOT_DAM_CRACK_09", 0.95)
    assert anomaly_alert is not None
    assert anomaly_alert.fault_type == FaultType.ANOMALY.value
    assert "Z-Score" in anomaly_alert.message


def test_level3_explainable_diagnostics_content(fault_engine):
    """Verifies physics-based diagnostic reasoning, equations, and inspection steps."""
    diag = fault_engine.generate_explainable_diagnostics(
        sensor_id="HECRAS_GATE02_PRESS",
        component_id="intake_gate",
        value=480.0,
        threshold=450.0,
        severity="CRITICAL"
    )
    assert "hydrostatic" in diag.summary.lower() or "surge" in diag.summary.lower()
    assert len(diag.potential_causes) >= 2
    assert len(diag.inspection_steps) >= 3
    assert "ΔP_joukowsky" in diag.governing_equation or "F_h" in diag.governing_equation
    assert diag.confidence_pct > 70.0


def test_multiple_simultaneous_faults(fault_engine):
    """Verifies multiple simultaneous active alerts on distinct components."""
    fault_engine.evaluate_sensor_reading("SCADA_TURB1_VIB_X", 9.1)
    fault_engine.evaluate_sensor_reading("IOT_DAM_CRACK_09", 2.2)
    fault_engine.evaluate_sensor_reading("SCADA_BEARING_TEMP_01", 79.0)

    assert len(fault_engine.active_alerts) == 3
    payloads = fault_engine.get_3d_highlight_payloads()
    assert len(payloads) == 3
    components_targeted = {p["component_id"] for p in payloads}
    assert "turbine_runner" in components_targeted
    assert "dam_structure" in components_targeted
    assert "generator_stator" in components_targeted
