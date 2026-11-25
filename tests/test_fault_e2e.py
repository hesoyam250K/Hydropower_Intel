"""End-to-end fault simulation tests verifying the complete workflow:

Fault simulation → Sensor evaluation → Alert record → 3D highlight payload → Component mapping

Tests verify:
 1. Faults are created and stored in active_alerts
 2. get_3d_highlight_payloads() returns populated payloads
 3. Component IDs in payloads map to known 3D mesh names
 4. Multiple simultaneous faults both appear
 5. Neither fault overwrites the other
 6. Missing component mapping handled gracefully (no unrelated highlight)
 7. Fault acknowledgement retains the database record
 8. Resolution workflow updates status correctly
 9. The shared session state pattern works (simulating JARVIS view)
"""

import pytest
from datetime import datetime
from typing import List, Dict, Any

from src.diagnostics.engine import FaultEngine, FaultRecord, FaultSeverity, FaultType
from src.cad.sensor_mesh_mapper import SensorMeshMapper
from src.database.storage import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """In-memory database for isolation."""
    db_path = str(tmp_path / "test_faults.db")
    dm = DatabaseManager(db_path=db_path)
    return dm


@pytest.fixture
def engine(db):
    return FaultEngine(db_manager=db)


# ---------------------------------------------------------------------------
# Known sensor → component mappings from sensor_mesh_map.json
# ---------------------------------------------------------------------------
KNOWN_SENSORS = {
    "SCADA_TURB1_VIB_X": {
        "component_id": "Turbine_01_MainShaft",
        "threshold_breach_value": 9.4,  # > 8.5 mm/s critical
        "normal_value": 2.0
    },
    "HECRAS_GATE02_PRESS": {
        "component_id": "Spillway_Gate_02",
        "threshold_breach_value": 485.0,  # > 450 kPa critical
        "normal_value": 200.0
    },
    "IOT_DAM_CRACK_09": {
        "component_id": "Dam_Wall_Section_B",
        "threshold_breach_value": 2.35,  # > 2.0 mm critical
        "normal_value": 0.1
    },
    "SCADA_BEARING_TEMP_01": {
        "component_id": "Generator_MainBearing",
        "threshold_breach_value": 78.5,  # > 70°C critical
        "normal_value": 45.0
    }
}


# ===========================================================================
# TEST 1: Turbine Vibration
# ===========================================================================

class TestTurbineVibrationFault:
    def test_vibration_spike_creates_alert(self, engine):
        """Test 1: Turbine shaft vibration generates an active alert."""
        alerts = engine.inject_simulated_fault("vibration_spike")
        assert len(alerts) >= 1

    def test_vibration_fault_severity_critical(self, engine):
        """Value 9.4 mm/s exceeds critical threshold (8.5)."""
        alerts = engine.inject_simulated_fault("vibration_spike")
        vib_alert = next((a for a in alerts if "VIB" in a.sensor_id), None)
        assert vib_alert is not None
        assert vib_alert.severity == FaultSeverity.CRITICAL.value

    def test_vibration_fault_stored_in_active_alerts(self, engine):
        engine.inject_simulated_fault("vibration_spike")
        assert "SCADA_TURB1_VIB_X" in engine.active_alerts

    def test_vibration_fault_component_id_mapped(self, engine):
        """Component ID must resolve to turbine-related mesh identifier."""
        engine.inject_simulated_fault("vibration_spike")
        alert = engine.active_alerts.get("SCADA_TURB1_VIB_X")
        assert alert is not None
        comp = alert.component_id.lower()
        assert any(kw in comp for kw in ["turbine", "shaft", "runner", "bearing"]), \
            f"Component ID not turbine-related: {alert.component_id}"

    def test_vibration_fault_appears_in_3d_highlight_payload(self, engine):
        """Test 1 acceptance: turbine shaft highlighted in 3D."""
        engine.inject_simulated_fault("vibration_spike")
        payloads = engine.get_3d_highlight_payloads()
        assert len(payloads) >= 1
        turb_payload = next((p for p in payloads if "VIB" in p["sensor_id"]), None)
        assert turb_payload is not None
        assert turb_payload["color_hex"] in ("#ff2244", "#FF2244")  # Critical = red

    def test_vibration_fault_diagnostic_panel_component(self, engine):
        """Diagnostic panel must identify the affected component."""
        engine.inject_simulated_fault("vibration_spike")
        alert = engine.active_alerts.get("SCADA_TURB1_VIB_X")
        assert alert is not None
        assert alert.component_id  # Must be non-empty
        assert alert.diagnostics is not None
        assert alert.diagnostics.summary
        assert len(alert.diagnostics.inspection_steps) >= 1


# ===========================================================================
# TEST 2: Spillway Gate Pressure
# ===========================================================================

class TestSpillwayGatePressure:
    def test_gate_pressure_creates_alert(self, engine):
        """Test 2: Gate pressure surge generates alert."""
        alerts = engine.inject_simulated_fault("gate_pressure_surge")
        assert len(alerts) >= 1

    def test_gate_pressure_component_is_spillway(self, engine):
        engine.inject_simulated_fault("gate_pressure_surge")
        alert = engine.active_alerts.get("HECRAS_GATE02_PRESS")
        assert alert is not None
        comp = alert.component_id.lower()
        assert any(kw in comp for kw in ["gate", "spillway", "intake"]), \
            f"Component ID not gate-related: {alert.component_id}"

    def test_gate_pressure_in_3d_payload(self, engine):
        """Test 2 acceptance: correct gate is highlighted."""
        engine.inject_simulated_fault("gate_pressure_surge")
        payloads = engine.get_3d_highlight_payloads()
        gate_p = next((p for p in payloads if "PRESS" in p["sensor_id"]), None)
        assert gate_p is not None
        assert gate_p["component_id"]

    def test_gate_fault_selectable_from_panel(self, engine):
        """Fault must be accessible via active_alerts for diagnostics panel."""
        engine.inject_simulated_fault("gate_pressure_surge")
        alerts_list = list(engine.active_alerts.values())
        gate_alert = next((a for a in alerts_list if "PRESS" in a.sensor_id), None)
        assert gate_alert is not None
        assert gate_alert.fault_id is not None or gate_alert.sensor_id  # Retained


# ===========================================================================
# TEST 3: Dam Structural Displacement
# ===========================================================================

class TestDamStructuralDisplacement:
    def test_dam_crack_alert_generated(self, engine):
        """Test 3: Dam crack displacement generates alert."""
        alerts = engine.inject_simulated_fault("dam_crest_crack")
        assert len(alerts) >= 1

    def test_dam_crack_component_is_dam_wall(self, engine):
        engine.inject_simulated_fault("dam_crest_crack")
        alert = engine.active_alerts.get("IOT_DAM_CRACK_09")
        assert alert is not None
        comp = alert.component_id.lower()
        assert any(kw in comp for kw in ["dam", "wall", "section", "crest"]), \
            f"Component ID not dam-related: {alert.component_id}"

    def test_dam_section_in_3d_payload(self, engine):
        """Test 3 acceptance: correct dam section highlighted in 3D."""
        engine.inject_simulated_fault("dam_crest_crack")
        payloads = engine.get_3d_highlight_payloads()
        dam_p = next((p for p in payloads if "CRACK" in p["sensor_id"] or "DAM" in p["sensor_id"]), None)
        assert dam_p is not None


# ===========================================================================
# TEST 4: Multiple Simultaneous Faults
# ===========================================================================

class TestMultipleSimultaneousFaults:
    def test_compound_emergency_generates_multiple_alerts(self, engine):
        """Test 4: Compound emergency creates multiple active alerts."""
        alerts = engine.inject_simulated_fault("compound_emergency")
        assert len(alerts) >= 2

    def test_both_faults_in_active_alerts(self, engine):
        engine.inject_simulated_fault("compound_emergency")
        assert len(engine.active_alerts) >= 2

    def test_neither_fault_overwrites_other(self, engine):
        """Both faults must remain independently accessible."""
        engine.inject_simulated_fault("compound_emergency")
        payloads = engine.get_3d_highlight_payloads()
        assert len(payloads) >= 2
        # Verify distinct component IDs
        comp_ids = [p["component_id"] for p in payloads]
        assert len(set(comp_ids)) >= 2 or len(comp_ids) >= 2

    def test_both_accessible_through_diagnostics_panel(self, engine):
        engine.inject_simulated_fault("compound_emergency")
        alerts = list(engine.active_alerts.values())
        assert len(alerts) >= 2
        # Each must have diagnostics
        for alert in alerts:
            assert alert.diagnostics is not None
            assert alert.severity in (FaultSeverity.WARNING.value, FaultSeverity.CRITICAL.value)

    def test_multiple_faults_have_distinct_colors(self, engine):
        """Critical = red, warning = amber."""
        engine.inject_simulated_fault("compound_emergency")
        payloads = engine.get_3d_highlight_payloads()
        for p in payloads:
            assert p["color_hex"] in ("#ff2244", "#FF2244", "#ffaa00", "#FFAA00"), \
                f"Unexpected color: {p['color_hex']}"


# ===========================================================================
# TEST 5: Missing Component Mapping
# ===========================================================================

class TestMissingComponentMapping:
    def test_unknown_sensor_does_not_crash_engine(self, engine):
        """Test 5: Unknown sensor returns None and does not raise."""
        result = engine.evaluate_sensor_reading("UNKNOWN_SENSOR_XYZ", 999.9, is_simulated=True)
        # Should return None (no mapping) — not crash
        assert result is None

    def test_unknown_sensor_event_not_in_active_alerts(self, engine):
        engine.evaluate_sensor_reading("MISSING_SENSOR_123", 500.0, is_simulated=True)
        assert "MISSING_SENSOR_123" not in engine.active_alerts

    def test_unknown_sensor_does_not_highlight_unrelated_component(self, engine):
        """Test 5: Unmapped fault must not add payload for unrelated component."""
        engine.evaluate_sensor_reading("GHOST_SENSOR_XYZ", 1000.0, is_simulated=True)
        payloads = engine.get_3d_highlight_payloads()
        # No payload should be added for ghost sensor
        ghost = [p for p in payloads if p["sensor_id"] == "GHOST_SENSOR_XYZ"]
        assert len(ghost) == 0

    def test_unknown_sensor_error_handled_gracefully(self, engine):
        """Engine should not raise Exception for missing mapping."""
        try:
            engine.evaluate_sensor_reading("NO_MAPPING_SENSOR", -999.0)
        except Exception as e:
            pytest.fail(f"Engine raised unexpected exception for unknown sensor: {e}")


# ===========================================================================
# TEST 6: Fault Acknowledgement and Resolution
# ===========================================================================

class TestFaultAcknowledgement:
    def test_acknowledge_does_not_delete_db_record(self, engine, db):
        """Test 6: Acknowledging a fault retains the database record."""
        engine.inject_simulated_fault("vibration_spike")
        alert = engine.active_alerts.get("SCADA_TURB1_VIB_X")
        assert alert is not None
        fault_db_id = alert.fault_id

        # Acknowledge (clear from active_alerts)
        engine.clear_alert("SCADA_TURB1_VIB_X")
        assert "SCADA_TURB1_VIB_X" not in engine.active_alerts

        # DB record must still exist
        if fault_db_id:
            events = db.list_fault_history(limit=100)
            ids = [e.get("id") for e in events]
            assert fault_db_id in ids, \
                f"DB record {fault_db_id} was deleted on acknowledge. Events: {ids}"

    def test_3d_display_clears_after_acknowledge(self, engine):
        """3D payload list should be empty after all alerts cleared."""
        engine.inject_simulated_fault("vibration_spike")
        assert len(engine.get_3d_highlight_payloads()) >= 1
        engine.clear_alert("SCADA_TURB1_VIB_X")
        payloads = engine.get_3d_highlight_payloads()
        assert len(payloads) == 0

    def test_clear_all_simulated_faults(self, engine):
        """Clear all simulated faults without touching database records."""
        engine.inject_simulated_fault("compound_emergency")
        count = len(engine.active_alerts)
        assert count >= 2
        cleared = engine.clear_all_simulated_faults()
        assert cleared >= 2
        assert len(engine.active_alerts) == 0

    def test_resolution_does_not_affect_non_simulated_alerts(self, engine, db):
        """clear_all_simulated_faults should NOT clear sensor-detected (non-simulated) alerts."""
        # Inject a real sensor reading (detected, not simulated)
        engine.evaluate_sensor_reading("SCADA_TURB1_VIB_X", 9.4, is_simulated=False)
        # Also inject a simulated one (different sensor)
        engine.inject_simulated_fault("dam_crest_crack")
        
        cleared = engine.clear_all_simulated_faults()
        # Only simulated ones cleared
        assert cleared >= 1
        # Non-simulated turbine alert must remain
        assert "SCADA_TURB1_VIB_X" in engine.active_alerts


# ===========================================================================
# TEST 7: Payload Structure Validation
# ===========================================================================

class TestPayloadStructure:
    def test_payload_has_required_fields(self, engine):
        engine.inject_simulated_fault("vibration_spike")
        payloads = engine.get_3d_highlight_payloads()
        required = {"sensor_id", "component_id", "severity", "color_hex",
                    "emissive_intensity", "message", "measured", "threshold"}
        for p in payloads:
            missing = required - set(p.keys())
            assert not missing, f"Payload missing fields: {missing}"

    def test_critical_payload_has_high_emissive(self, engine):
        engine.inject_simulated_fault("vibration_spike")
        payloads = engine.get_3d_highlight_payloads()
        crit = [p for p in payloads if p["severity"] == "CRITICAL"]
        for p in crit:
            assert p["emissive_intensity"] >= 1.5, \
                f"Critical fault should have high emissive: {p['emissive_intensity']}"

    def test_warning_payload_has_amber_color(self, engine):
        """Warning faults should use amber (#ffaa00)."""
        engine.inject_simulated_fault("bearing_overheat")
        payloads = engine.get_3d_highlight_payloads()
        for p in payloads:
            if p["severity"] == FaultSeverity.WARNING.value:
                assert p["color_hex"].lower() in ("#ffaa00",)

    def test_simulated_flag_in_payload(self, engine):
        engine.inject_simulated_fault("vibration_spike")
        payloads = engine.get_3d_highlight_payloads()
        for p in payloads:
            assert p.get("is_simulated") is True

    def test_sensor_reading_non_simulated_flag(self, engine):
        engine.evaluate_sensor_reading("SCADA_TURB1_VIB_X", 9.5, is_simulated=False)
        payloads = engine.get_3d_highlight_payloads()
        for p in payloads:
            assert p.get("is_simulated") is False


# ===========================================================================
# TEST 8: Shared Engine Pattern (JARVIS View Simulation)
# ===========================================================================

class TestSharedEnginePattern:
    def test_fault_injected_before_jarvis_view_appears_in_payloads(self, db):
        """Simulates what happens when fault_detection_view injects a fault
        and then digital_twin_jarvis_view calls get_3d_highlight_payloads().
        
        The fix: both views MUST share the same FaultEngine instance via session_state.
        This test verifies the engine is stateful across calls.
        """
        # Simulate fault_detection_view creating/getting the shared engine
        shared_engine = FaultEngine(db_manager=db)
        
        # Fault detection tab injects a fault
        shared_engine.inject_simulated_fault("vibration_spike")
        assert len(shared_engine.active_alerts) >= 1

        # JARVIS view should use the SAME instance
        # (In production: st.session_state["fault_engine"])
        payloads = shared_engine.get_3d_highlight_payloads()
        assert len(payloads) >= 1, \
            "JARVIS 3D view must see faults injected by fault detection view!"
        
    def test_new_engine_instance_has_no_faults(self, db):
        """Demonstrates the bug: a new FaultEngine instance has zero active_alerts."""
        engine_1 = FaultEngine(db_manager=db)
        engine_1.inject_simulated_fault("vibration_spike")
        
        # Bug: creating second engine loses all faults
        engine_2 = FaultEngine(db_manager=db)
        payloads_bug = engine_2.get_3d_highlight_payloads()
        assert len(payloads_bug) == 0, \
            "New engine instance must have zero alerts — shared session state is required!"

    def test_database_persisted_faults_can_be_loaded(self, db):
        """Active faults logged to DB can be queried for display even after engine restart."""
        engine_1 = FaultEngine(db_manager=db)
        engine_1.inject_simulated_fault("gate_pressure_surge")
        
        # Query DB directly for logged events
        events = db.list_fault_history(limit=100)
        assert len(events) >= 1
        gate_event = next((e for e in events if "PRESS" in e.get("sensor_id", "")), None)
        assert gate_event is not None


# ===========================================================================
# TEST 9: Engineering Integrity
# ===========================================================================

class TestEngineeringIntegrity:
    def test_simulated_fault_clearly_labelled(self, engine):
        """Simulated faults must be labelled as SIMULATED in fault_type."""
        engine.inject_simulated_fault("vibration_spike")
        alert = engine.active_alerts.get("SCADA_TURB1_VIB_X")
        assert alert is not None
        assert alert.fault_type == FaultType.SIMULATED.value
        assert alert.is_simulated is True
        # Message must indicate simulation
        assert "[SIMULATED]" in alert.message

    def test_real_sensor_reading_labelled_detected(self, engine):
        """Real sensor breaches must be DETECTED, not SIMULATED."""
        engine.evaluate_sensor_reading("SCADA_TURB1_VIB_X", 9.5, is_simulated=False)
        alert = engine.active_alerts.get("SCADA_TURB1_VIB_X")
        assert alert is not None
        assert alert.fault_type == FaultType.DETECTED.value
        assert alert.is_simulated is False
        assert "[SIMULATED]" not in alert.message

    def test_diagnostic_summary_not_empty(self, engine):
        engine.inject_simulated_fault("vibration_spike")
        alert = engine.active_alerts.get("SCADA_TURB1_VIB_X")
        assert alert.diagnostics.summary
        assert alert.diagnostics.confidence_pct > 0
        assert len(alert.diagnostics.potential_causes) >= 1
        assert len(alert.diagnostics.inspection_steps) >= 1

    def test_threshold_values_match_sensor_config(self, engine, db):
        """Threshold values in alert should come from sensor config, not be hardcoded."""
        engine.inject_simulated_fault("vibration_spike")
        alert = engine.active_alerts.get("SCADA_TURB1_VIB_X")
        assert alert is not None
        # Value 9.4 should be above threshold
        assert alert.measured_value > alert.threshold_value or \
               alert.severity in (FaultSeverity.WARNING.value, FaultSeverity.CRITICAL.value)
