"""Local SQLite persistent storage layer for HydroPower Intelligence.

Ensures projects, calculations, simulation logs, and settings survive application restarts.
Operates completely offline without external database servers.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "hydropower_intelligence.db"
)


class DatabaseManager:
    """Manages SQLite connection lifecycle and schema operations."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def connection_scope(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a safe connection context that always closes on exit."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Initializes tables for projects, calculations, simulations, telemetry, and settings."""
        with self.connection_scope() as conn:
            cursor = conn.cursor()

            # 1. Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    location TEXT,
                    river_name TEXT,
                    description TEXT,
                    gross_head_m REAL DEFAULT 25.0,
                    design_flow_lps REAL DEFAULT 1000.0,
                    efficiency REAL DEFAULT 0.82,
                    pipe_diameter_m REAL DEFAULT 0.50,
                    pipe_length_m REAL DEFAULT 150.0,
                    roughness_mm REAL DEFAULT 0.045,
                    turbine_type TEXT DEFAULT 'Francis Reaction Turbine',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Calculation history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    name TEXT NOT NULL,
                    inputs_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
            """)

            # 3. Simulation runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    scenario_name TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
            """)

            # 4. Telemetry historical logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,  -- 'SIMULATED' or 'PHYSICAL_MQTT'
                    flow_lps REAL,
                    net_head_m REAL,
                    power_kw REAL,
                    frequency_hz REAL,
                    voltage_v REAL,
                    current_a REAL,
                    gate_position_pct REAL,
                    alerts_json TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
                );
            """)

            # 5. Application settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 6. CAD/BIM Imported Models
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imported_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    name TEXT NOT NULL,
                    format TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    component_count INTEGER DEFAULT 0,
                    vertex_count INTEGER DEFAULT 0,
                    face_count INTEGER DEFAULT 0,
                    bounds_json TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
            """)

            # 7. Model Sub-Components Hierarchy
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id INTEGER,
                    component_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    global_id TEXT,
                    category TEXT,
                    bounds_json TEXT,
                    properties_json TEXT,
                    FOREIGN KEY (model_id) REFERENCES imported_models(id) ON DELETE CASCADE
                );
            """)

            # 8. Sensor to 3D Component Mappings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    sensor_id TEXT NOT NULL UNIQUE,
                    sensor_name TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    warning_threshold REAL NOT NULL,
                    critical_threshold REAL NOT NULL,
                    comparison_op TEXT DEFAULT '>',
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
            """)

            # 9. Fault Detection & Anomaly Events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fault_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    sensor_id TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    fault_type TEXT NOT NULL,
                    measured_value REAL NOT NULL,
                    threshold_value REAL NOT NULL,
                    message TEXT NOT NULL,
                    diagnostics_json TEXT,
                    is_simulated INTEGER DEFAULT 0,
                    is_cleared INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    cleared_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
                );
            """)

            # 10. Physical Turbine & IoT Hardware Devices
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS physical_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    connection_type TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    status TEXT DEFAULT 'DISCONNECTED',
                    last_seen_at TEXT,
                    created_at TEXT NOT NULL
                );
            """)

        # Seed default project and default sensor mappings if needed
        self._seed_default_project()
        self._seed_default_sensor_mappings()

    def _seed_default_project(self) -> None:
        """Seeds an educational sample project for civil/mechanical engineering students."""
        projects = self.list_projects()
        if not projects:
            self.create_project(
                name="Clearwater River Small Hydro Demo",
                location="Cascade Range, Oregon",
                river_name="Clearwater Creek",
                description="Run-of-river small hydropower scheme with intake weir, surface penstock, and Francis turbine powerhouse.",
                gross_head_m=32.0,
                design_flow_lps=1250.0,
                efficiency=0.84,
                pipe_diameter_m=0.60,
                pipe_length_m=180.0,
                roughness_mm=0.045,
                turbine_type="Francis Reaction Turbine"
            )

    # ==================== Project CRUD ====================

    def create_project(
        self,
        name: str,
        location: str = "",
        river_name: str = "",
        description: str = "",
        gross_head_m: float = 25.0,
        design_flow_lps: float = 1000.0,
        efficiency: float = 0.82,
        pipe_diameter_m: float = 0.50,
        pipe_length_m: float = 150.0,
        roughness_mm: float = 0.045,
        turbine_type: str = "Francis Reaction Turbine"
    ) -> int:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO projects (
                    name, location, river_name, description, gross_head_m, design_flow_lps,
                    efficiency, pipe_diameter_m, pipe_length_m, roughness_mm, turbine_type,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, location, river_name, description, gross_head_m, design_flow_lps,
                efficiency, pipe_diameter_m, pipe_length_m, roughness_mm, turbine_type,
                now, now
            ))
            return cursor.lastrowid

    def list_projects(self) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_project(self, project_id: int, **kwargs) -> bool:
        allowed = {
            "name", "location", "river_name", "description", "gross_head_m",
            "design_flow_lps", "efficiency", "pipe_diameter_m", "pipe_length_m",
            "roughness_mm", "turbine_type"
        }
        fields = [f"{k} = ?" for k in kwargs if k in allowed]
        if not fields:
            return False

        fields.append("updated_at = ?")
        values = [kwargs[k] for k in kwargs if k in allowed]
        values.append(datetime.now().isoformat())
        values.append(project_id)

        query = f"UPDATE projects SET {', '.join(fields)} WHERE id = ?"
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))
            return cursor.rowcount > 0

    def delete_project(self, project_id: int) -> bool:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    # ==================== Calculations ====================

    def save_calculation(
        self,
        project_id: Optional[int],
        name: str,
        inputs: Dict[str, Any],
        results: Dict[str, Any],
        notes: str = ""
    ) -> int:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO calculations (project_id, name, inputs_json, results_json, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                name,
                json.dumps(inputs),
                json.dumps(results),
                notes,
                now
            ))
            return cursor.lastrowid

    def list_calculations(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT * FROM calculations WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,)
                )
            else:
                cursor.execute("SELECT * FROM calculations ORDER BY created_at DESC")
            rows = cursor.fetchall()
            output = []
            for row in rows:
                d = dict(row)
                d["inputs"] = json.loads(d["inputs_json"])
                d["results"] = json.loads(d["results_json"])
                output.append(d)
            return output

    def delete_calculation(self, calc_id: int) -> bool:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM calculations WHERE id = ?", (calc_id,))
            return cursor.rowcount > 0

    # ==================== Simulations ====================

    def save_simulation(
        self,
        project_id: Optional[int],
        scenario_name: str,
        params: Dict[str, Any],
        summary: Dict[str, Any]
    ) -> int:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO simulations (project_id, scenario_name, params_json, summary_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                project_id,
                scenario_name,
                json.dumps(params),
                json.dumps(summary),
                now
            ))
            return cursor.lastrowid

    def list_simulations(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT * FROM simulations WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,)
                )
            else:
                cursor.execute("SELECT * FROM simulations ORDER BY created_at DESC")
            rows = cursor.fetchall()
            output = []
            for row in rows:
                d = dict(row)
                d["params"] = json.loads(d["params_json"])
                d["summary"] = json.loads(d["summary_json"])
                output.append(d)
            return output

    # ==================== Telemetry Logs ====================

    def log_telemetry_point(
        self,
        source: str,
        flow_lps: float,
        net_head_m: float,
        power_kw: float,
        frequency_hz: float,
        voltage_v: float,
        current_a: float,
        gate_position_pct: float,
        alerts: Optional[List[str]] = None,
        project_id: Optional[int] = None,
        timestamp: Optional[str] = None
    ) -> int:
        ts = timestamp or datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telemetry_logs (
                    project_id, timestamp, source, flow_lps, net_head_m, power_kw,
                    frequency_hz, voltage_v, current_a, gate_position_pct, alerts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, ts, source, flow_lps, net_head_m, power_kw,
                frequency_hz, voltage_v, current_a, gate_position_pct,
                json.dumps(alerts or [])
            ))
            return cursor.lastrowid

    def get_recent_telemetry(
        self,
        limit: int = 100,
        source: Optional[str] = None,
        project_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM telemetry_logs"
            clauses = []
            params = []
            if source:
                clauses.append("source = ?")
                params.append(source)
            if project_id:
                clauses.append("project_id = ?")
                params.append(project_id)

            if clauses:
                query += " WHERE " + " AND ".join(clauses)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for row in reversed(rows):
                d = dict(row)
                d["alerts"] = json.loads(d["alerts_json"]) if d["alerts_json"] else []
                results.append(d)
            return results

    # ==================== Settings ====================

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["value_json"])
            return default

    def set_setting(self, key: str, value: Any) -> None:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """, (key, json.dumps(value), now))

    def _seed_default_sensor_mappings(self) -> None:
        """Seeds default sensor-to-mesh mappings based on the master blueprint."""
        default_mappings = [
            ("SCADA_TURB1_VIB_X", "Turbine Shaft Vibration X", "Shaft Vibration", "mm/s", "turbine_runner", 4.5, 8.5, ">"),
            ("HECRAS_GATE02_PRESS", "Spillway Headgate Hydrostatic Pressure", "Hydrostatic Pressure", "kPa", "intake_gate", 380.0, 450.0, ">"),
            ("IOT_DAM_CRACK_09", "Dam Crest Joint Displacement", "Concrete Displacement", "mm", "dam_structure", 1.2, 2.0, ">"),
            ("SCADA_BEARING_TEMP_01", "Generator Main Thrust Bearing Temp", "Bearing Temperature", "°C", "generator_stator", 65.0, 75.0, ">"),
            ("IOT_PENSTOCK_SURGE_01", "Penstock Transient Hydraulic Surge", "Water Hammer Pressure", "bar", "penstock_pipe", 18.0, 22.0, ">"),
            ("IOT_BRIDGE_STRESS_01", "Thermal Bridge Restrained Stress", "Thermal Stress", "MPa", "thermal_bridge_regions", 20.0, 30.0, ">"),
            ("IOT_JOINT_TRAVEL_01", "Elastomeric Joint Thermal Travel", "Joint Movement", "mm", "expansion_joints", 30.0, 45.0, ">"),
            ("IOT_TURBINE_RPM_01", "Turbine Runner Rotational Velocity", "Rotational Speed", "RPM", "turbine_runner", 1200.0, 1450.0, ">"),
        ]
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM sensor_mappings")
            row = cursor.fetchone()
            if row and row["cnt"] == 0:
                for s_id, s_name, metric, unit, comp_id, warn, crit, op in default_mappings:
                    cursor.execute("""
                        INSERT OR IGNORE INTO sensor_mappings (
                            sensor_id, sensor_name, metric, unit, component_id,
                            warning_threshold, critical_threshold, comparison_op, is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (s_id, s_name, metric, unit, comp_id, warn, crit, op))

    # ==================== CAD/BIM Imported Models ====================

    def save_imported_model(
        self,
        name: str,
        format_type: str,
        file_path: str,
        project_id: Optional[int] = None,
        component_count: int = 0,
        vertex_count: int = 0,
        face_count: int = 0,
        bounds: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO imported_models (
                    project_id, name, format, file_path, component_count,
                    vertex_count, face_count, bounds_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, name, format_type.upper(), file_path, component_count,
                vertex_count, face_count,
                json.dumps(bounds or {}),
                json.dumps(metadata or {}),
                now
            ))
            return cursor.lastrowid

    def list_imported_models(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute("SELECT * FROM imported_models WHERE project_id = ? ORDER BY id DESC", (project_id,))
            else:
                cursor.execute("SELECT * FROM imported_models ORDER BY id DESC")
            rows = cursor.fetchall()
            output = []
            for r in rows:
                d = dict(r)
                d["bounds"] = json.loads(d["bounds_json"]) if d["bounds_json"] else {}
                d["metadata"] = json.loads(d["metadata_json"]) if d["metadata_json"] else {}
                output.append(d)
            return output

    def get_imported_model(self, model_id: int) -> Optional[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM imported_models WHERE id = ?", (model_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["bounds"] = json.loads(d["bounds_json"]) if d["bounds_json"] else {}
            d["metadata"] = json.loads(d["metadata_json"]) if d["metadata_json"] else {}
            return d

    def delete_imported_model(self, model_id: int) -> bool:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM imported_models WHERE id = ?", (model_id,))
            return cursor.rowcount > 0

    def save_model_components(self, model_id: int, components: List[Dict[str, Any]]) -> int:
        count = 0
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            for c in components:
                cursor.execute("""
                    INSERT INTO model_components (
                        model_id, component_id, name, global_id, category, bounds_json, properties_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    model_id,
                    c.get("component_id", ""),
                    c.get("name", ""),
                    c.get("global_id", ""),
                    c.get("category", "civil"),
                    json.dumps(c.get("bounds", {})),
                    json.dumps(c.get("properties", {}))
                ))
                count += 1
        return count

    def list_model_components(self, model_id: int) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_components WHERE model_id = ? ORDER BY id ASC", (model_id,))
            rows = cursor.fetchall()
            output = []
            for r in rows:
                d = dict(r)
                d["bounds"] = json.loads(d["bounds_json"]) if d["bounds_json"] else {}
                d["properties"] = json.loads(d["properties_json"]) if d["properties_json"] else {}
                output.append(d)
            return output

    # ==================== Sensor Mappings ====================

    def create_or_update_sensor_mapping(
        self,
        sensor_id: str,
        sensor_name: str,
        metric: str,
        unit: str,
        component_id: str,
        warning_threshold: float,
        critical_threshold: float,
        comparison_op: str = ">",
        project_id: Optional[int] = None,
        is_active: int = 1
    ) -> int:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_mappings (
                    sensor_id, sensor_name, metric, unit, component_id,
                    warning_threshold, critical_threshold, comparison_op, is_active, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sensor_id) DO UPDATE SET
                    sensor_name = excluded.sensor_name,
                    metric = excluded.metric,
                    unit = excluded.unit,
                    component_id = excluded.component_id,
                    warning_threshold = excluded.warning_threshold,
                    critical_threshold = excluded.critical_threshold,
                    comparison_op = excluded.comparison_op,
                    is_active = excluded.is_active,
                    project_id = excluded.project_id
            """, (
                sensor_id, sensor_name, metric, unit, component_id,
                warning_threshold, critical_threshold, comparison_op, is_active, project_id
            ))
            return cursor.lastrowid

    def list_sensor_mappings(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT * FROM sensor_mappings WHERE project_id = ? OR project_id IS NULL ORDER BY sensor_id ASC",
                    (project_id,)
                )
            else:
                cursor.execute("SELECT * FROM sensor_mappings ORDER BY sensor_id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_sensor_mapping(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sensor_mappings WHERE sensor_id = ?", (sensor_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_sensor_mapping(self, sensor_id: str) -> bool:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sensor_mappings WHERE sensor_id = ?", (sensor_id,))
            return cursor.rowcount > 0

    # ==================== Fault Events ====================

    def log_fault_event(
        self,
        sensor_id: str,
        component_id: str,
        severity: str,
        fault_type: str,
        measured_value: float,
        threshold_value: float,
        message: str,
        diagnostics: Optional[Dict[str, Any]] = None,
        is_simulated: int = 0,
        project_id: Optional[int] = None,
        timestamp: Optional[str] = None
    ) -> int:
        ts = timestamp or datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fault_events (
                    project_id, sensor_id, component_id, severity, fault_type,
                    measured_value, threshold_value, message, diagnostics_json,
                    is_simulated, is_cleared, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                project_id, sensor_id, component_id, severity.upper(), fault_type.upper(),
                float(measured_value), float(threshold_value), message,
                json.dumps(diagnostics or {}), int(is_simulated), ts
            ))
            return cursor.lastrowid

    def list_active_faults(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT * FROM fault_events WHERE is_cleared = 0 AND (project_id = ? OR project_id IS NULL) ORDER BY id DESC",
                    (project_id,)
                )
            else:
                cursor.execute("SELECT * FROM fault_events WHERE is_cleared = 0 ORDER BY id DESC")
            rows = cursor.fetchall()
            output = []
            for r in rows:
                d = dict(r)
                d["diagnostics"] = json.loads(d["diagnostics_json"]) if d["diagnostics_json"] else {}
                output.append(d)
            return output

    def list_fault_history(self, limit: int = 50, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute(
                    "SELECT * FROM fault_events WHERE (project_id = ? OR project_id IS NULL) ORDER BY id DESC LIMIT ?",
                    (project_id, limit)
                )
            else:
                cursor.execute("SELECT * FROM fault_events ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            output = []
            for r in rows:
                d = dict(r)
                d["diagnostics"] = json.loads(d["diagnostics_json"]) if d["diagnostics_json"] else {}
                output.append(d)
            return output

    def clear_fault_event(self, fault_id: int) -> bool:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE fault_events SET is_cleared = 1, cleared_at = ? WHERE id = ?", (now, fault_id))
            return cursor.rowcount > 0

    def clear_all_simulated_faults(self, project_id: Optional[int] = None) -> int:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute("UPDATE fault_events SET is_cleared = 1, cleared_at = ? WHERE is_simulated = 1 AND is_cleared = 0 AND (project_id = ? OR project_id IS NULL)", (now, project_id))
            else:
                cursor.execute("UPDATE fault_events SET is_cleared = 1, cleared_at = ? WHERE is_simulated = 1 AND is_cleared = 0", (now,))
            return cursor.rowcount

    # ==================== Physical Hardware Devices ====================

    def save_physical_device(
        self,
        name: str,
        device_type: str,
        connection_type: str,
        config: Dict[str, Any],
        status: str = "DISCONNECTED"
    ) -> int:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO physical_devices (
                    name, device_type, connection_type, config_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (name, device_type, connection_type, json.dumps(config), status, now))
            return cursor.lastrowid

    def list_physical_devices(self) -> List[Dict[str, Any]]:
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM physical_devices ORDER BY id DESC")
            rows = cursor.fetchall()
            output = []
            for r in rows:
                d = dict(r)
                d["config"] = json.loads(d["config_json"]) if d["config_json"] else {}
                output.append(d)
            return output

    def update_device_status(self, device_id: int, status: str) -> bool:
        now = datetime.now().isoformat()
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE physical_devices SET status = ?, last_seen_at = ? WHERE id = ?", (status, now, device_id))
            return cursor.rowcount > 0
