"""Fault Detection and Diagnostics Engine for HydroPower Intelligence.

Features:
- Level 1: Rule-based engineering thresholds, range validation, rate-of-change checks
- Level 2: Statistical anomaly detection (rolling Z-score, IQR, outlier detection)
- Level 3: Physics-grounded explainable diagnostics and inspection checklists
- Sensor-to-mesh 3D binding and alert lifecycle management
"""

from src.diagnostics.engine import (
    FaultEngine,
    FaultSeverity,
    FaultType,
    FaultRecord,
    DiagnosticExplanation,
)

__all__ = [
    "FaultEngine",
    "FaultSeverity",
    "FaultType",
    "FaultRecord",
    "DiagnosticExplanation",
]
