"""Sensor Adapters and Measurement Signal Processing for Physical Turbine Demonstrator.

Transforms raw micro-controller ADC voltages, pulse counts, and bus registers into
calibrated civil/mechanical engineering physical quantities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple, Union


class SensorType(str, Enum):
    FLOW = "FLOW"
    PRESSURE = "PRESSURE"
    RPM = "RPM"
    VIBRATION = "VIBRATION"
    TEMPERATURE = "TEMPERATURE"
    VOLTAGE = "VOLTAGE"
    CURRENT = "CURRENT"


@dataclass
class SensorReading:
    """Standardized engineering measurement packet."""
    sensor_type: str
    sensor_id: str
    raw_signal: float
    engineering_value: Optional[float]
    unit: str
    status: str  # 'OK', 'OUT_OF_RANGE', 'DISCONNECTED', 'MISSING'
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    calibration_factor: float = 1.0
    zero_offset: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_type": self.sensor_type,
            "sensor_id": self.sensor_id,
            "raw_signal": round(self.raw_signal, 3),
            "engineering_value": round(self.engineering_value, 2) if self.engineering_value is not None else None,
            "unit": self.unit,
            "status": self.status,
            "timestamp": self.timestamp
        }


class FlowSensorAdapter:
    """Converts Hall-effect paddlewheel/turbine pulse frequency (Hz) or 4-20mA to L/s and m³/s."""

    def __init__(self, pulses_per_liter: float = 4.5, max_flow_lps: float = 2500.0):
        self.pulses_per_liter = pulses_per_liter
        self.max_flow_lps = max_flow_lps

    def process(self, raw_input: Optional[float], sensor_id: str = "FLOW_01", is_freq: bool = True) -> SensorReading:
        if raw_input is None:
            return SensorReading(SensorType.FLOW.value, sensor_id, 0.0, None, "L/s", "MISSING")
        if raw_input < 0 or raw_input > 20000:
            return SensorReading(SensorType.FLOW.value, sensor_id, raw_input, None, "L/s", "OUT_OF_RANGE")

        if is_freq:
            flow_lps = raw_input / max(0.1, self.pulses_per_liter)
        else:
            # 4-20mA current loop: 4mA = 0 L/s, 20mA = max_flow_lps
            norm = max(0.0, min(1.0, (raw_input - 4.0) / 16.0))
            flow_lps = norm * self.max_flow_lps

        return SensorReading(
            sensor_type=SensorType.FLOW.value,
            sensor_id=sensor_id,
            raw_signal=raw_input,
            engineering_value=flow_lps,
            unit="L/s",
            status="OK" if flow_lps <= self.max_flow_lps else "OUT_OF_RANGE",
            calibration_factor=self.pulses_per_liter
        )


class PressureSensorAdapter:
    """Converts 0.5-4.5V ratiometric pressure transducer signal to kPa and bar."""

    def __init__(self, min_volts: float = 0.5, max_volts: float = 4.5, max_pressure_kpa: float = 1000.0):
        self.min_volts = min_volts
        self.max_volts = max_volts
        self.max_kpa = max_pressure_kpa

    def process(self, volts: Optional[float], sensor_id: str = "PRESS_01") -> SensorReading:
        if volts is None:
            return SensorReading(SensorType.PRESSURE.value, sensor_id, 0.0, None, "kPa", "MISSING")
        if volts < 0.2 or volts > 5.5:
            return SensorReading(SensorType.PRESSURE.value, sensor_id, volts, None, "kPa", "DISCONNECTED")

        span = self.max_volts - self.min_volts
        norm = max(0.0, (volts - self.min_volts) / span)
        kpa = norm * self.max_kpa

        return SensorReading(
            sensor_type=SensorType.PRESSURE.value,
            sensor_id=sensor_id,
            raw_signal=volts,
            engineering_value=kpa,
            unit="kPa",
            status="OK" if kpa <= (self.max_kpa * 1.1) else "OUT_OF_RANGE"
        )


class RPMSensorAdapter:
    """Converts optical or magnetic pulse timing to turbine shaft rotational speed (RPM)."""

    def __init__(self, pulses_per_rev: int = 1):
        self.pulses_per_rev = max(1, pulses_per_rev)

    def process(self, pulse_freq_hz: Optional[float], sensor_id: str = "RPM_01") -> SensorReading:
        if pulse_freq_hz is None:
            return SensorReading(SensorType.RPM.value, sensor_id, 0.0, None, "RPM", "MISSING")
        if pulse_freq_hz < 0:
            return SensorReading(SensorType.RPM.value, sensor_id, pulse_freq_hz, None, "RPM", "OUT_OF_RANGE")

        rpm = (pulse_freq_hz * 60.0) / self.pulses_per_rev
        return SensorReading(
            sensor_type=SensorType.RPM.value,
            sensor_id=sensor_id,
            raw_signal=pulse_freq_hz,
            engineering_value=rpm,
            unit="RPM",
            status="OK" if rpm <= 3600.0 else "OUT_OF_RANGE"
        )


class VibrationSensorAdapter:
    """Converts raw accelerometer g-force / ADC counts into ISO 10816 RMS velocity (mm/s)."""

    def __init__(self, sensitivity_mv_per_g: float = 100.0):
        self.sensitivity = sensitivity_mv_per_g

    def process(self, raw_mv: Optional[float], sensor_id: str = "SCADA_TURB1_VIB_X") -> SensorReading:
        if raw_mv is None:
            return SensorReading(SensorType.VIBRATION.value, sensor_id, 0.0, None, "mm/s", "MISSING")

        # Convert peak mV to acceleration g, then integrate to RMS velocity mm/s assuming ~25-50Hz fundamental
        g_force = abs(raw_mv) / max(1.0, self.sensitivity)
        # Empirical conversion for 50Hz machine: 1 g peak ~ 22.1 mm/s RMS
        vibe_mms = g_force * 22.1

        return SensorReading(
            sensor_type=SensorType.VIBRATION.value,
            sensor_id=sensor_id,
            raw_signal=raw_mv,
            engineering_value=vibe_mms,
            unit="mm/s",
            status="OK"
        )


class TemperatureSensorAdapter:
    """Processes digital 1-Wire (DS18B20) or analog RTD temperature signals."""

    def process(self, deg_c: Optional[float], sensor_id: str = "TEMP_BEARING_01") -> SensorReading:
        if deg_c is None:
            return SensorReading(SensorType.TEMPERATURE.value, sensor_id, 0.0, None, "°C", "MISSING")
        # DS18B20 85°C indicates power-on reset failure, -127°C indicates disconnected line
        if deg_c == -127.0 or deg_c < -40.0:
            return SensorReading(SensorType.TEMPERATURE.value, sensor_id, deg_c, None, "°C", "DISCONNECTED")
        if deg_c > 150.0:
            return SensorReading(SensorType.TEMPERATURE.value, sensor_id, deg_c, None, "°C", "OUT_OF_RANGE")

        return SensorReading(
            sensor_type=SensorType.TEMPERATURE.value,
            sensor_id=sensor_id,
            raw_signal=deg_c,
            engineering_value=deg_c,
            unit="°C",
            status="OK"
        )


class ElectricalSensorAdapter:
    """Processes AC generator electrical metrics: RMS Voltage, Current, and Real Power."""

    def __init__(self, is_three_phase: bool = True, default_power_factor: float = 0.88):
        self.is_three_phase = is_three_phase
        self.default_pf = default_power_factor

    def process(
        self,
        voltage_v: Optional[float],
        current_a: Optional[float],
        power_factor: Optional[float] = None,
        sensor_id: str = "ELEC_METER_01"
    ) -> Tuple[SensorReading, SensorReading, SensorReading]:
        """Returns (VoltageReading, CurrentReading, ActivePowerReading in kW)."""
        v = voltage_v if voltage_v is not None else 0.0
        i = current_a if current_a is not None else 0.0
        pf = power_factor if (power_factor is not None and 0.0 <= power_factor <= 1.0) else self.default_pf

        v_reading = SensorReading(
            sensor_type=SensorType.VOLTAGE.value,
            sensor_id=f"{sensor_id}_V",
            raw_signal=v,
            engineering_value=v if voltage_v is not None else None,
            unit="V",
            status="OK" if (0.0 <= v <= 1000.0 and voltage_v is not None) else ("MISSING" if voltage_v is None else "OUT_OF_RANGE")
        )

        i_reading = SensorReading(
            sensor_type=SensorType.CURRENT.value,
            sensor_id=f"{sensor_id}_A",
            raw_signal=i,
            engineering_value=i if current_a is not None else None,
            unit="A",
            status="OK" if (0.0 <= i <= 5000.0 and current_a is not None) else ("MISSING" if current_a is None else "OUT_OF_RANGE")
        )

        # Calculate Active Electrical Power:
        # 3-Phase: P = sqrt(3) * V * I * cos(phi) / 1000 (kW)
        # Single-Phase: P = V * I * cos(phi) / 1000 (kW)
        if voltage_v is not None and current_a is not None:
            multiplier = math.sqrt(3.0) if self.is_three_phase else 1.0
            power_kw = (multiplier * v * i * pf) / 1000.0
            p_status = "OK"
        else:
            power_kw = None
            p_status = "MISSING"

        p_reading = SensorReading(
            sensor_type="POWER",
            sensor_id=f"{sensor_id}_P",
            raw_signal=power_kw if power_kw is not None else 0.0,
            engineering_value=power_kw,
            unit="kW",
            status=p_status
        )

        return v_reading, i_reading, p_reading
