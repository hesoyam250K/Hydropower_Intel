"""Sensor management and threshold validation for live telemetry streams.

Defines:
- TelemetryDataPoint structure
- Operating thresholds (Normal, Warning, Fault)
- Machinery health standards (ISO 10816 vibration, bearing temperatures)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TelemetryThresholds:
    """Configurable operational boundaries for hydropower telemetry."""
    min_flow_lps: float = 100.0
    max_flow_lps: float = 2500.0
    min_head_m: float = 10.0
    max_head_m: float = 50.0
    min_power_kw: float = 5.0
    max_power_kw: float = 500.0
    min_frequency_hz: float = 49.5
    max_frequency_hz: float = 50.5
    min_voltage_v: float = 380.0
    max_voltage_v: float = 420.0
    max_current_a: float = 450.0
    max_bearing_temp_c: float = 70.0  # Max allowable continuous bearing oil temp
    max_vibration_mms: float = 4.5  # ISO 10816 Zone C warning boundary (mm/s RMS)


@dataclass
class TelemetryDataPoint:
    """Represents a single telemetry sensor packet."""
    timestamp: str
    source: str  # 'SIMULATED' or 'PHYSICAL_MQTT'
    flow_lps: float
    net_head_m: float
    power_kw: float
    frequency_hz: float
    voltage_v: float
    current_a: float
    gate_position_pct: float
    bearing_temp_c: float = 42.0
    vibration_mms: float = 1.2
    status_level: str = "NORMAL"  # 'NORMAL', 'WARNING', 'ALARM'
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "flow_lps": round(self.flow_lps, 2),
            "net_head_m": round(self.net_head_m, 2),
            "power_kw": round(self.power_kw, 2),
            "frequency_hz": round(self.frequency_hz, 2),
            "voltage_v": round(self.voltage_v, 1),
            "current_a": round(self.current_a, 1),
            "gate_position_pct": round(self.gate_position_pct, 1),
            "bearing_temp_c": round(self.bearing_temp_c, 1),
            "vibration_mms": round(self.vibration_mms, 2),
            "status_level": self.status_level,
            "alerts": self.alerts,
        }


def evaluate_telemetry_point(
    point: TelemetryDataPoint,
    thresholds: Optional[TelemetryThresholds] = None
) -> TelemetryDataPoint:
    """Evaluates telemetry data point against engineering thresholds and attaches alerts."""
    th = thresholds or TelemetryThresholds()
    alerts: List[str] = []
    level = "NORMAL"

    def upgrade_level(new_level: str):
        nonlocal level
        if new_level == "ALARM" or level == "ALARM":
            level = "ALARM"
        elif new_level == "WARNING" or level == "WARNING":
            level = "WARNING"

    # Frequency check (grid synchronization)
    if point.frequency_hz < th.min_frequency_hz or point.frequency_hz > th.max_frequency_hz:
        alerts.append(f"Grid Frequency Out of Bounds ({point.frequency_hz:.2f} Hz, target 50.00 Hz)")
        freq_sev = "WARNING" if abs(point.frequency_hz - 50.0) < 1.0 else "ALARM"
        upgrade_level(freq_sev)

    # Bearing temperature check
    if point.bearing_temp_c > th.max_bearing_temp_c:
        alerts.append(f"High Bearing Temperature ({point.bearing_temp_c:.1f} °C > {th.max_bearing_temp_c} °C threshold)")
        temp_sev = "ALARM" if point.bearing_temp_c > (th.max_bearing_temp_c + 5.0) else "WARNING"
        upgrade_level(temp_sev)

    # Vibration check
    if point.vibration_mms > th.max_vibration_mms:
        alerts.append(f"Elevated Mechanical Vibration ({point.vibration_mms:.2f} mm/s RMS > ISO 10816 limit)")
        vib_sev = "ALARM" if point.vibration_mms > 7.1 else "WARNING"
        upgrade_level(vib_sev)

    # Flow check
    if point.flow_lps < th.min_flow_lps and point.gate_position_pct > 20.0:
        alerts.append(f"Low Flow Alert ({point.flow_lps:.1f} L/s with open gate; potential intake obstruction)")
        upgrade_level("WARNING")

    # Voltage check
    if point.voltage_v < th.min_voltage_v or point.voltage_v > th.max_voltage_v:
        alerts.append(f"Generator Line Voltage Deviation ({point.voltage_v:.1f} V)")
        upgrade_level("WARNING")

    point.status_level = level
    point.alerts = alerts
    return point
