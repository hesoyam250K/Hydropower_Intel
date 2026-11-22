"""Unit tests for SQLite persistent storage layer."""

import os
import tempfile
import pytest
from src.database.storage import DatabaseManager


@pytest.fixture
def temp_db():
    """Provides an isolated temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    yield db
    import gc
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except (PermissionError, OSError):
        pass


def test_project_crud(temp_db):
    """Tests creating, reading, updating, and deleting projects."""
    # List initial seeded project
    projects = temp_db.list_projects()
    assert len(projects) == 1
    assert "Clearwater" in projects[0]["name"]

    # Create new project
    pid = temp_db.create_project(
        name="Highland Gorge Hydro",
        location="Scottish Highlands",
        river_name="Gorge Burn",
        gross_head_m=120.0,
        design_flow_lps=450.0,
    )
    assert pid > 0

    p = temp_db.get_project(pid)
    assert p["name"] == "Highland Gorge Hydro"
    assert p["gross_head_m"] == 120.0

    # Update project
    updated = temp_db.update_project(pid, gross_head_m=125.0, efficiency=0.88)
    assert updated is True
    p2 = temp_db.get_project(pid)
    assert p2["gross_head_m"] == 125.0
    assert p2["efficiency"] == 0.88

    # Delete project
    deleted = temp_db.delete_project(pid)
    assert deleted is True
    assert temp_db.get_project(pid) is None


def test_calculation_history(temp_db):
    """Tests saving and retrieving calculation snapshots."""
    projects = temp_db.list_projects()
    pid = projects[0]["id"]

    calc_id = temp_db.save_calculation(
        project_id=pid,
        name="Design Flow Evaluation",
        inputs={"flow_lps": 1000.0, "gross_head_m": 25.0},
        results={"power_kw": 201.1, "energy_kwh": 4826.4},
        notes="Evaluated for winter high-flow scenario."
    )
    assert calc_id > 0

    calcs = temp_db.list_calculations(project_id=pid)
    assert len(calcs) == 1
    assert calcs[0]["name"] == "Design Flow Evaluation"
    assert calcs[0]["inputs"]["flow_lps"] == 1000.0
    assert calcs[0]["results"]["power_kw"] == 201.1


def test_simulation_history(temp_db):
    """Tests storing and retrieving simulation run summaries."""
    projects = temp_db.list_projects()
    pid = projects[0]["id"]

    sim_id = temp_db.save_simulation(
        project_id=pid,
        scenario_name="Load Rejection Transient",
        params={"duration_s": 30.0, "gate_speed": 5.0},
        summary={"max_head_surge_m": 42.5, "peak_speed_rpm": 1280.0}
    )
    assert sim_id > 0

    sims = temp_db.list_simulations(project_id=pid)
    assert len(sims) == 1
    assert sims[0]["scenario_name"] == "Load Rejection Transient"
    assert sims[0]["summary"]["max_head_surge_m"] == 42.5


def test_telemetry_logging(temp_db):
    """Tests recording and querying telemetry points."""
    temp_db.log_telemetry_point(
        source="SIMULATED",
        flow_lps=980.5,
        net_head_m=28.4,
        power_kw=185.2,
        frequency_hz=50.02,
        voltage_v=401.2,
        current_a=266.5,
        gate_position_pct=82.0,
        alerts=["Normal Operating Mode"]
    )

    logs = temp_db.get_recent_telemetry(limit=10, source="SIMULATED")
    assert len(logs) == 1
    assert logs[0]["flow_lps"] == 980.5
    assert logs[0]["alerts"] == ["Normal Operating Mode"]


def test_settings_storage(temp_db):
    """Tests key-value settings persistence."""
    temp_db.set_setting("units_flow", "L/s")
    temp_db.set_setting("mqtt_broker", {"host": "localhost", "port": 1883})

    assert temp_db.get_setting("units_flow") == "L/s"
    assert temp_db.get_setting("mqtt_broker")["port"] == 1883
    assert temp_db.get_setting("non_existent", "default_val") == "default_val"
