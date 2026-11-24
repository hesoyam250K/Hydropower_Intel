"""Physical Hydropower Turbine Hardware Integration Package.

Provides:
- Sensor adapters for flow, pressure, RPM, vibration, temperature, voltage, and current
- Serial (ESP32) and MQTT communication handlers
- Virtual, Hardware, and Hybrid digital-twin operating modes
- Theoretical vs measured hydropower and electrical efficiency comparison
"""

from src.hardware.sensor_adapters import (
    SensorType,
    SensorReading,
    FlowSensorAdapter,
    PressureSensorAdapter,
    RPMSensorAdapter,
    VibrationSensorAdapter,
    TemperatureSensorAdapter,
    ElectricalSensorAdapter,
)
from src.hardware.turbine_interface import (
    OperatingMode,
    TurbineTelemetryPacket,
    PhysicalTurbineManager,
)

__all__ = [
    "SensorType",
    "SensorReading",
    "FlowSensorAdapter",
    "PressureSensorAdapter",
    "RPMSensorAdapter",
    "VibrationSensorAdapter",
    "TemperatureSensorAdapter",
    "ElectricalSensorAdapter",
    "OperatingMode",
    "TurbineTelemetryPacket",
    "PhysicalTurbineManager",
]
