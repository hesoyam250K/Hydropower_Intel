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

        # Seed default project if database is completely empty
        self._seed_default_project()

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
