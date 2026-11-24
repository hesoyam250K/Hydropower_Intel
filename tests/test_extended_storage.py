"""Unit tests for extended SQLite schema: CAD models, sensor mappings, fault events, and IoT devices."""

import os
import tempfile
import pytest

from src.database.storage import DatabaseManager


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    yield db
    import gc
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def test_default_sensor_mappings_seeded(temp_db):
    """Verifies default blueprint sensor mappings are seeded into database."""
    mappings = temp_db.list_sensor_mappings()
    assert len(mappings) >= 8

    sensor_ids = {m["sensor_id"] for m in mappings}
    assert "SCADA_TURB1_VIB_X" in sensor_ids
    assert "HECRAS_GATE02_PRESS" in sensor_ids
    assert "IOT_DAM_CRACK_09" in sensor_ids
    assert "SCADA_BEARING_TEMP_01" in sensor_ids


def test_imported_model_and_components_crud(temp_db):
    """Verifies saving, retrieving, and deleting imported CAD/BIM models."""
    projects = temp_db.list_projects()
    pid = projects[0]["id"]

    model_id = temp_db.save_imported_model(
        project_id=pid,
        name="Francis_Turbine_Assembly",
        format_type="STEP",
        file_path="data/models/turbine.glb",
        component_count=5,
        vertex_count=12000,
        face_count=8500,
        bounds={"min_x": -5, "max_x": 5},
        metadata={"schema": "AP242"}
    )
    assert model_id > 0

    components = [
        {"component_id": "Turbine_Rotor", "name": "Runner Blades", "global_id": "G1", "category": "Mechanical"},
        {"component_id": "Turbine_Shaft", "name": "Main Shaft", "global_id": "G2", "category": "Mechanical"}
    ]
    saved_count = temp_db.save_model_components(model_id, components)
    assert saved_count == 2

    # Query back
    m = temp_db.get_imported_model(model_id)
    assert m["name"] == "Francis_Turbine_Assembly"
    assert m["format"] == "STEP"
    assert m["vertex_count"] == 12000

    comps = temp_db.list_model_components(model_id)
    assert len(comps) == 2
    assert comps[0]["component_id"] == "Turbine_Rotor"

    # Delete
    deleted = temp_db.delete_imported_model(model_id)
    assert deleted is True
    assert temp_db.get_imported_model(model_id) is None


def test_fault_event_logging_and_clearing(temp_db):
    """Verifies logging fault events and managing active alert lifecycle in SQLite."""
    projects = temp_db.list_projects()
    pid = projects[0]["id"]

    fid1 = temp_db.log_fault_event(
        sensor_id="SCADA_TURB1_VIB_X",
        component_id="turbine_runner",
        severity="CRITICAL",
        fault_type="DETECTED",
        measured_value=9.4,
        threshold_value=8.5,
        message="Critical shaft vibration",
        project_id=pid
    )
    assert fid1 > 0

    fid2 = temp_db.log_fault_event(
        sensor_id="HECRAS_GATE02_PRESS",
        component_id="intake_gate",
        severity="WARNING",
        fault_type="SIMULATED",
        measured_value=410.0,
        threshold_value=380.0,
        message="Simulated gate pressure surge",
        is_simulated=1,
        project_id=pid
    )
    assert fid2 > 0

    active = temp_db.list_active_faults(project_id=pid)
    assert len(active) == 2

    # Clear simulated
    cleared_count = temp_db.clear_all_simulated_faults(project_id=pid)
    assert cleared_count == 1

    remaining_active = temp_db.list_active_faults(project_id=pid)
    assert len(remaining_active) == 1
    assert remaining_active[0]["sensor_id"] == "SCADA_TURB1_VIB_X"

    # Clear individual
    temp_db.clear_fault_event(fid1)
    assert len(temp_db.list_active_faults(project_id=pid)) == 0


def test_physical_devices_crud(temp_db):
    """Verifies registering and updating physical IoT/PLC devices."""
    dev_id = temp_db.save_physical_device(
        name="ESP32_Turbine_Gate_Node",
        device_type="ESP32",
        connection_type="SERIAL",
        config={"port": "COM3", "baud": 115200},
        status="DISCONNECTED"
    )
    assert dev_id > 0

    devices = temp_db.list_physical_devices()
    assert len(devices) >= 1
    assert devices[0]["name"] == "ESP32_Turbine_Gate_Node"
    assert devices[0]["config"]["baud"] == 115200

    temp_db.update_device_status(dev_id, "CONNECTED")
    devices_updated = temp_db.list_physical_devices()
    assert devices_updated[0]["status"] == "CONNECTED"
