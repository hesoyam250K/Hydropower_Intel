"""Synthetic telemetry data generator for offline simulation and testing.

Generates physically consistent, reproducible sensor readings:
- Flow rate with realistic turbulent fluctuations
- Net head and penstock pressure
- Electrical parameters (3-phase Voltage, Current, Frequency, Active Power)
- Machinery health metrics (Bearing Temperature, ISO 10816 Vibration)
All data points are explicitly tagged as SIMULATED.
"""

import math
import random
import time
from datetime import datetime
from typing import Optional

from src.telemetry.sensor_manager import (
    TelemetryDataPoint,
    TelemetryThresholds,
    evaluate_telemetry_point,
)


class SimulatedTelemetryGenerator:
    """Stateful, reproducible generator of synthetic hydropower plant telemetry."""

    def __init__(
        self,
        base_flow_lps: float = 1200.0,
        base_head_m: float = 30.0,
        base_efficiency: float = 0.84,
        rated_voltage_v: float = 400.0,
        nominal_frequency_hz: float = 50.0,
        power_factor: float = 0.88,
        seed: Optional[int] = 42
    ):
        self.base_flow_lps = base_flow_lps
        self.base_head_m = base_head_m
        self.base_efficiency = base_efficiency
        self.rated_voltage_v = rated_voltage_v
        self.nominal_frequency_hz = nominal_frequency_hz
        self.power_factor = power_factor

        self.step_count = 0
        self.gate_position_pct = 80.0
        self.bearing_temp_c = 42.0

        # Disturbance flags
        self.injected_low_flow: bool = False
        self.injected_frequency_trip: bool = False
        self.injected_bearing_fault: bool = False
        self.injected_vibration_spike: bool = False

        if seed is not None:
            random.seed(seed)

    def trigger_disturbance(self, disturbance_type: str, enable: bool = True) -> None:
        """Injects or clears operational faults for demonstration and training."""
        if disturbance_type == "low_flow":
            self.injected_low_flow = enable
        elif disturbance_type == "frequency_trip":
            self.injected_frequency_trip = enable
        elif disturbance_type == "bearing_fault":
            self.injected_bearing_fault = enable
        elif disturbance_type == "vibration_spike":
            self.injected_vibration_spike = enable

    def generate_next_point(
        self,
        timestamp: Optional[str] = None,
        thresholds: Optional[TelemetryThresholds] = None
    ) -> TelemetryDataPoint:
        """Generates the next continuous synthetic telemetry reading."""
        self.step_count += 1
        t_sec = self.step_count * 1.0
        ts = timestamp or datetime.now().isoformat()

        # 1. Flow rate with slight harmonic river turbulence + random micro-noise
        noise_flow = random.gauss(0.0, 15.0)
        harmonic_flow = 25.0 * math.sin(t_sec / 15.0) + 10.0 * math.cos(t_sec / 7.0)
        target_flow = self.base_flow_lps * (self.gate_position_pct / 100.0)

        if self.injected_low_flow:
            # Simulate upstream blockage / debris rack clogging
            target_flow *= 0.35

        flow_lps = max(0.0, target_flow + harmonic_flow + noise_flow)
        flow_m3s = flow_lps / 1000.0

        # 2. Net Head with friction response
        head_noise = random.gauss(0.0, 0.15)
        # Higher flow causes greater friction drop: h_f ~ k * Q^2
        head_friction_drop = 2.0 * ((flow_lps / self.base_flow_lps) ** 2)
        net_head = max(0.5, self.base_head_m - head_friction_drop + head_noise)

        # 3. Active Electrical Power: P = rho * g * Q * H_net * eta
        # Fresh water density 1000, g = 9.81
        p_hyd_kw = 9.81 * flow_m3s * net_head
        power_kw = max(0.0, p_hyd_kw * self.base_efficiency)

        # 4. Generator 3-phase Voltage and Current
        # P_3phase = sqrt(3) * V_LL * I_L * cos(phi)
        # I_L = (P * 1000) / (sqrt(3) * V_LL * cos(phi))
        v_noise = random.gauss(0.0, 1.2)
        voltage_v = max(300.0, self.rated_voltage_v + v_noise)

        denom = math.sqrt(3.0) * voltage_v * self.power_factor
        current_a = (power_kw * 1000.0) / denom if denom > 0 else 0.0

        # 5. Grid Frequency
        freq_noise = random.gauss(0.0, 0.02)
        if self.injected_frequency_trip:
            freq_hz = 51.4 + random.gauss(0.0, 0.05)  # Severe overfrequency
        else:
            freq_hz = round(self.nominal_frequency_hz + freq_noise, 2)

        # 6. Bearing Temperature and Vibration
        if self.injected_bearing_fault:
            self.bearing_temp_c = min(88.0, self.bearing_temp_c + 0.8)
        else:
            # Thermal equilibrium around 45°C depending on load
            target_temp = 38.0 + (power_kw / 20.0)
            self.bearing_temp_c += (target_temp - self.bearing_temp_c) * 0.05 + random.gauss(0.0, 0.1)

        base_vib = 1.2 + (power_kw / 300.0)
        if self.injected_vibration_spike:
            vibration_mms = 5.8 + abs(random.gauss(0.0, 0.5))
        else:
            vibration_mms = max(0.2, base_vib + abs(random.gauss(0.0, 0.2)))

        point = TelemetryDataPoint(
            timestamp=ts,
            source="SIMULATED",
            flow_lps=flow_lps,
            net_head_m=net_head,
            power_kw=power_kw,
            frequency_hz=freq_hz,
            voltage_v=voltage_v,
            current_a=current_a,
            gate_position_pct=self.gate_position_pct,
            bearing_temp_c=self.bearing_temp_c,
            vibration_mms=vibration_mms
        )

        return evaluate_telemetry_point(point, thresholds)
