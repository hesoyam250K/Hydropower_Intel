"""Core Engineering Fault Detection, Anomaly Screening, and Explainable Diagnostics Engine.

Connects physical sensors, SCADA streams, and hydraulic simulations to 3D sub-components.
"""

from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from src.cad.sensor_mesh_mapper import SensorMeshMapper
from src.database.storage import DatabaseManager


class FaultSeverity(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class FaultType(str, Enum):
    DETECTED = "DETECTED"    # Confirmed threshold breach from live sensors
    ANOMALY = "ANOMALY"      # Statistical outlier / abnormal historical pattern
    SIMULATED = "SIMULATED"  # Controlled fault injection scenario
    MANUAL = "MANUAL"        # Operator logged defect


@dataclass
class DiagnosticExplanation:
    """Physics-grounded root-cause hypothesis and operator inspection procedure."""
    summary: str
    potential_causes: List[str]
    inspection_steps: List[str]
    governing_equation: str
    confidence_pct: float
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FaultRecord:
    """An active or logged engineering fault event mapped to a digital-twin component."""
    fault_id: Optional[int]
    sensor_id: str
    component_id: str
    severity: str  # 'NORMAL', 'WARNING', 'CRITICAL', 'UNKNOWN'
    fault_type: str  # 'DETECTED', 'ANOMALY', 'SIMULATED', 'MANUAL'
    measured_value: float
    threshold_value: float
    unit: str
    message: str
    diagnostics: DiagnosticExplanation
    is_simulated: bool = False
    is_cleared: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    cleared_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["diagnostics"] = self.diagnostics.to_dict()
        return d


class FaultEngine:
    """Comprehensive Fault Detection and Diagnostic Engine.

    Levels:
    - Level 1: Deterministic threshold checks, operating boundary validation, invalid sensor values, rate of change
    - Level 2: Statistical anomaly detection (rolling Z-scores, standard deviation bands)
    - Level 3: Physics-grounded explainable diagnostics and mitigation procedures
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        mesh_mapper: Optional[SensorMeshMapper] = None
    ):
        self.db = db_manager or DatabaseManager()
        self.mapper = mesh_mapper or SensorMeshMapper()
        # Active in-memory alerts indexed by sensor_id
        self.active_alerts: Dict[str, FaultRecord] = {}
        # Historical sliding windows for Level 2 statistical anomaly detection
        self.history_windows: Dict[str, deque] = {}
        self.history_timestamps: Dict[str, deque] = {}
        self.window_size = 50

    # =========================================================================
    # Level 1: Rule-Based Evaluation
    # =========================================================================

    def evaluate_sensor_reading(
        self,
        sensor_id: str,
        value: float,
        is_simulated: bool = False,
        project_id: Optional[int] = None,
        timestamp: Optional[str] = None
    ) -> Optional[FaultRecord]:
        """Evaluates a single sensor measurement against engineering limits."""
        ts = timestamp or datetime.now().isoformat()

        # Update sliding history window for anomaly screening
        if sensor_id not in self.history_windows:
            self.history_windows[sensor_id] = deque(maxlen=self.window_size)
            self.history_timestamps[sensor_id] = deque(maxlen=self.window_size)
        self.history_windows[sensor_id].append(value)
        self.history_timestamps[sensor_id].append(ts)

        # Retrieve rule configuration
        mapping = self.db.get_sensor_mapping(sensor_id)
        if not mapping:
            # Fall back to default mapper configuration
            data = self.mapper.mappings.get(sensor_id)
            if data:
                mapping = {
                    "sensor_id": sensor_id,
                    "sensor_name": data.get("metric", sensor_id),
                    "metric": data.get("metric", "Measurement"),
                    "unit": data.get("unit", ""),
                    "component_id": data.get("component_id", "turbine_runner"),
                    "warning_threshold": data.get("warning_threshold", 100.0),
                    "critical_threshold": data.get("critical_threshold", 150.0),
                    "comparison_op": data.get("comparison", ">"),
                    "is_active": 1
                }
            else:
                return None

        if not mapping.get("is_active", 1):
            return None

        comp_id = mapping.get("component_id", "turbine_runner")
        warn_th = float(mapping.get("warning_threshold", 100.0))
        crit_th = float(mapping.get("critical_threshold", 150.0))
        op = mapping.get("comparison_op", ">")
        unit = mapping.get("unit", "")
        metric = mapping.get("metric", sensor_id)

        # Check validity (NaN or Inf)
        if math.isnan(value) or math.isinf(value):
            return self._create_or_update_alert(
                sensor_id=sensor_id,
                comp_id=comp_id,
                severity=FaultSeverity.CRITICAL.value,
                fault_type=FaultType.DETECTED.value if not is_simulated else FaultType.SIMULATED.value,
                measured_val=value,
                thresh_val=crit_th,
                unit=unit,
                message=f"Sensor Error: Invalid float ({value}) on {sensor_id}",
                project_id=project_id,
                is_simulated=is_simulated,
                ts=ts
            )

        # Determine severity
        severity = FaultSeverity.NORMAL.value
        breach_th = warn_th

        if op == ">":
            if value >= crit_th:
                severity = FaultSeverity.CRITICAL.value
                breach_th = crit_th
            elif value >= warn_th:
                severity = FaultSeverity.WARNING.value
                breach_th = warn_th
        elif op == "<":
            if value <= crit_th:
                severity = FaultSeverity.CRITICAL.value
                breach_th = crit_th
            elif value <= warn_th:
                severity = FaultSeverity.WARNING.value
                breach_th = warn_th

        if severity == FaultSeverity.NORMAL.value:
            # Check Level 2 statistical anomaly if rule threshold is not breached
            anomaly_alert = self.check_statistical_anomaly(sensor_id, value, is_simulated, project_id, ts)
            if anomaly_alert:
                return anomaly_alert

            # Value returned to normal range: clear any active alert
            if sensor_id in self.active_alerts:
                self.clear_alert(sensor_id)
            return None

        # Level 1 fault breach detected
        msg = f"{'[SIMULATED] ' if is_simulated else ''}{metric} exceeded {severity.lower()} limit: {value:.2f} {unit} ({op} {breach_th:.2f} {unit})"
        return self._create_or_update_alert(
            sensor_id=sensor_id,
            comp_id=comp_id,
            severity=severity,
            fault_type=FaultType.SIMULATED.value if is_simulated else FaultType.DETECTED.value,
            measured_val=value,
            thresh_val=breach_th,
            unit=unit,
            message=msg,
            project_id=project_id,
            is_simulated=is_simulated,
            ts=ts
        )

    # =========================================================================
    # Level 2: Statistical Anomaly Detection
    # =========================================================================

    def check_statistical_anomaly(
        self,
        sensor_id: str,
        current_value: float,
        is_simulated: bool = False,
        project_id: Optional[int] = None,
        ts: Optional[str] = None
    ) -> Optional[FaultRecord]:
        """Detects statistical outliers over sliding historical window using Z-score."""
        history = list(self.history_windows.get(sensor_id, []))
        if len(history) < 15:
            # Insufficient samples for statistical significance
            return None

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std_dev = math.sqrt(variance)

        if std_dev < 1e-4:
            return None

        z_score = abs(current_value - mean) / std_dev

        if z_score >= 3.2:
            comp_id = self.mapper.get_component_id(sensor_id) or "turbine_runner"
            mapping = self.mapper.mappings.get(sensor_id, {})
            unit = mapping.get("unit", "")
            metric = mapping.get("metric", sensor_id)

            msg = (
                f"{'[SIMULATED] ' if is_simulated else ''}Statistical Anomaly on {metric}: "
                f"Z-Score = {z_score:.2f}σ (Value: {current_value:.2f} {unit}, Window Mean: {mean:.2f} ± {std_dev:.2f})"
            )

            diag = DiagnosticExplanation(
                summary=f"Unusual statistical deviation detected in {metric} sensor stream.",
                potential_causes=[
                    "Early onset bearing raceway spalling",
                    "Sensor electrical interference or loose signal wiring",
                    "Transient hydraulic flow turbulence or vortex shedding"
                ],
                inspection_steps=[
                    "Check sensor terminal connections and cable shielding",
                    "Compare against redundant secondary transducer if installed",
                    "Perform high-frequency FFT acoustic emission testing"
                ],
                governing_equation="Z = |x - μ| / σ > 3.0 (Gaussian 3-sigma anomaly boundary)",
                confidence_pct=85.0,
                evidence={"z_score": round(z_score, 2), "sample_count": len(history), "window_mean": round(mean, 2)}
            )

            alert = FaultRecord(
                fault_id=None,
                sensor_id=sensor_id,
                component_id=comp_id,
                severity=FaultSeverity.WARNING.value,
                fault_type=FaultType.ANOMALY.value,
                measured_value=current_value,
                threshold_value=mean + 3.0 * std_dev,
                unit=unit,
                message=msg,
                diagnostics=diag,
                is_simulated=is_simulated,
                timestamp=ts or datetime.now().isoformat()
            )
            self.active_alerts[sensor_id] = alert
            return alert

        return None

    # =========================================================================
    # Level 3: Explainable Engineering Diagnostics
    # =========================================================================

    def generate_explainable_diagnostics(
        self,
        sensor_id: str,
        component_id: str,
        value: float,
        threshold: float,
        severity: str
    ) -> DiagnosticExplanation:
        """Generates physics-based, explainable engineering hypotheses and inspection steps."""

        if "VIB" in sensor_id or "turbine" in component_id:
            return DiagnosticExplanation(
                summary="Severe mechanical vibration detected along turbine shaft line exceeding ISO 10816 Zone D trip limits.",
                potential_causes=[
                    "Runner hydraulic unbalance due to sediment erosion or blade cavitation",
                    "Radial guide bearing clearance degradation or loss of hydrodynamic lubrication film",
                    "Generator-turbine shaft angular/parallel misalignment",
                    "Part-load vortex core (draft tube surge) inducing low-frequency pressure pulsations"
                ],
                inspection_steps=[
                    "Perform vibration spectral FFT: check 1X rotational unbalance and 2X misalignment harmonics",
                    "Inspect turbine lower guide bearing oil sump temperature and metal debris chip detectors",
                    "Inspect runner suction surface for cavitation pitting and leading-edge erosion",
                    "Verify guide vane servo-cylinder timing to confirm balanced opening angles"
                ],
                governing_equation="F_unbalance = m_eccentric × r × ω² | Dynamic Shaft Displacement Limit: S_max ≤ 1.2 × S_allowable",
                confidence_pct=92.0 if severity == "CRITICAL" else 78.0,
                evidence={"vibration_rms_mms": value, "iso_10816_limit": threshold, "severity": severity}
            )

        elif "PRESS" in sensor_id or "gate" in component_id:
            return DiagnosticExplanation(
                summary="Hydrostatic / hydrodynamic surge pressure exceeded design safety allowance on intake headgate.",
                potential_causes=[
                    "Rapid penstock emergency gate closure inducing positive water hammer pressure rise",
                    "Upstream flood surge or debris blockage on forebay trash racks",
                    "Air vent pipe blockage creating severe pressure transients during gate movement"
                ],
                inspection_steps=[
                    "Check downstream penstock pressure transmitter for Joukowsky water hammer wave reflection",
                    "Inspect trash rack differential head loss transducers for debris accumulation",
                    "Verify penstock air-valve and pressure relief bypass valve operation",
                    "Examine gate skin plate and radial arm trunnion bearings for structural deformation"
                ],
                governing_equation="ΔP_joukowsky = ρ × a × ΔV | Hydrostatic Thrust: F_h = 0.5 × ρ × g × H² × B",
                confidence_pct=88.0,
                evidence={"measured_pressure_kpa": value, "design_threshold_kpa": threshold}
            )

        elif "CRACK" in sensor_id or "dam" in component_id:
            return DiagnosticExplanation(
                summary="Crest contraction joint structural displacement exceeds allowable thermal expansion allowance.",
                potential_causes=[
                    "Seasonal low ambient temperature inducing thermal contraction of monolith blocks",
                    "Differential foundation settlement or excessive hydrostatic uplift at dam heel",
                    "Alkali-silica reaction (ASR) swelling in adjacent concrete monolith blocks"
                ],
                inspection_steps=[
                    "Inspect copper or PVC waterstop seals inside inspection gallery for leakage",
                    "Read foundation uplift piezometers and drainage curtain discharge weir rates",
                    "Perform inverted pendulum and 3D total station structural geodetic survey",
                    "Verify structural temperature sensors across monolith concrete mass"
                ],
                governing_equation="ΔL = α_concrete × L_monolith × ΔT | Restrained Thermal Stress: σ = E × α × ΔT × R",
                confidence_pct=85.0,
                evidence={"measured_displacement_mm": value, "joint_limit_mm": threshold}
            )

        elif "TEMP" in sensor_id or "bearing" in component_id or "generator" in component_id:
            return DiagnosticExplanation(
                summary="High thermal rise detected on electrical generator stator / thrust bearing.",
                potential_causes=[
                    "Loss of bearing cooling water flow or heat exchanger tube fouling",
                    "Oil viscosity degradation or water contamination in lubricating sump",
                    "Electrical stator core phase unbalance or harmonic heating",
                    "Excessive hydraulic thrust load due to clogged runner balance holes"
                ],
                inspection_steps=[
                    "Check bearing lubricating oil circulation pump pressure and level",
                    "Inspect cooling water circuit flow transmitter and strainer differential pressure",
                    "Collect lubricating oil sample for viscosity and moisture analysis",
                    "Verify runner pressure relief balance chamber drain lines"
                ],
                governing_equation="Q_heat = (1 - η_bearing) × P_shaft | Heat Dissipation: Q = U × A × LMTD",
                confidence_pct=90.0,
                evidence={"measured_temp_c": value, "max_allowable_temp_c": threshold}
            )

        elif "STRESS" in sensor_id or "bridge" in component_id:
            return DiagnosticExplanation(
                summary="Excessive restrained thermal stress detected at hydrothermal bridge contact saddles.",
                potential_causes=[
                    "Sliding elastomeric or PTFE bearings frozen / locked due to corrosion or debris",
                    "Steep temperature gradient between hydrothermal fluid conduit and ambient winter air",
                    "Differential thermal expansion between steel conduit and concrete box girder deck"
                ],
                inspection_steps=[
                    "Inspect PTFE sliding plate surfaces and elastomeric pads for binding",
                    "Verify modular expansion finger joint gaps at north and south bridge abutments",
                    "Check thermal insulation cladding integrity along exposed conduit spans"
                ],
                governing_equation="σ_restrained = R × E × α × (T_fluid - T_datum) ≤ 0.6 × f_yield",
                confidence_pct=86.0,
                evidence={"measured_stress_mpa": value, "allowable_stress_mpa": threshold}
            )

        else:
            return DiagnosticExplanation(
                summary=f"Operational limit exceeded on {sensor_id}.",
                potential_causes=["Subsystem off-design operating condition", "Sensor calibration drift"],
                inspection_steps=["Perform local instrument verification", "Inspect physical component"],
                governing_equation="Threshold Boundary Check",
                confidence_pct=70.0,
                evidence={"measured_val": value, "threshold_val": threshold}
            )

    # =========================================================================
    # Alert Lifecycle & 3D Visual Binding
    # =========================================================================

    def _create_or_update_alert(
        self,
        sensor_id: str,
        comp_id: str,
        severity: str,
        fault_type: str,
        measured_val: float,
        thresh_val: float,
        unit: str,
        message: str,
        project_id: Optional[int],
        is_simulated: bool,
        ts: str
    ) -> FaultRecord:
        """Constructs fault record, persists in SQLite, and updates active alerts dictionary."""
        diag = self.generate_explainable_diagnostics(
            sensor_id=sensor_id,
            component_id=comp_id,
            value=measured_val,
            threshold=thresh_val,
            severity=severity
        )

        # Log event to database
        db_id = self.db.log_fault_event(
            sensor_id=sensor_id,
            component_id=comp_id,
            severity=severity,
            fault_type=fault_type,
            measured_value=measured_val,
            threshold_value=thresh_val,
            message=message,
            diagnostics=diag.to_dict(),
            is_simulated=1 if is_simulated else 0,
            project_id=project_id,
            timestamp=ts
        )

        record = FaultRecord(
            fault_id=db_id,
            sensor_id=sensor_id,
            component_id=comp_id,
            severity=severity,
            fault_type=fault_type,
            measured_value=measured_val,
            threshold_value=thresh_val,
            unit=unit,
            message=message,
            diagnostics=diag,
            is_simulated=is_simulated,
            is_cleared=False,
            timestamp=ts
        )

        self.active_alerts[sensor_id] = record
        return record

    def clear_alert(self, sensor_id: str) -> None:
        """Clears an active alert and updates database status."""
        record = self.active_alerts.pop(sensor_id, None)
        if record and record.fault_id:
            self.db.clear_fault_event(record.fault_id)

    def clear_all_simulated_faults(self) -> int:
        """Resets all injected test faults back to nominal baseline."""
        sim_sensors = [s_id for s_id, a in self.active_alerts.items() if a.is_simulated]
        for s_id in sim_sensors:
            self.clear_alert(s_id)
        return len(sim_sensors)

    def get_3d_highlight_payloads(self) -> List[Dict[str, Any]]:
        """Generates JSON-ready highlight payloads for Three.js / JARVIS 3D viewer."""
        payloads = []
        for alert in self.active_alerts.values():
            color_hex = "#ff2244" if alert.severity == FaultSeverity.CRITICAL.value else "#ffaa00"
            payloads.append({
                "sensor_id": alert.sensor_id,
                "component_id": alert.component_id,
                "severity": alert.severity,
                "fault_type": alert.fault_type,
                "color_hex": color_hex,
                "emissive_intensity": 1.8 if alert.severity == FaultSeverity.CRITICAL.value else 1.2,
                "message": alert.message,
                "measured": f"{alert.measured_value:.2f} {alert.unit}",
                "threshold": f"{alert.threshold_value:.2f} {alert.unit}",
                "is_simulated": alert.is_simulated,
                "timestamp": alert.timestamp
            })
        return payloads

    def inject_simulated_fault(
        self,
        scenario: str,
        project_id: Optional[int] = None
    ) -> List[FaultRecord]:
        """Injects a controlled, clearly-labelled simulated fault scenario."""
        scenarios: Dict[str, List[Tuple[str, float]]] = {
            "vibration_spike": [("SCADA_TURB1_VIB_X", 9.4)],
            "gate_pressure_surge": [("HECRAS_GATE02_PRESS", 485.0)],
            "dam_crest_crack": [("IOT_DAM_CRACK_09", 2.35)],
            "bearing_overheat": [("SCADA_BEARING_TEMP_01", 78.5)],
            "compound_emergency": [
                ("SCADA_TURB1_VIB_X", 9.2),
                ("SCADA_BEARING_TEMP_01", 76.0),
                ("IOT_PENSTOCK_SURGE_01", 24.5)
            ]
        }

        readings = scenarios.get(scenario, [("SCADA_TURB1_VIB_X", 9.5)])
        generated = []
        for s_id, val in readings:
            alert = self.evaluate_sensor_reading(
                sensor_id=s_id,
                value=val,
                is_simulated=True,
                project_id=project_id
            )
            if alert:
                generated.append(alert)
        return generated
