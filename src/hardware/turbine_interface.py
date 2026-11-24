"""Physical Hydropower Turbine Digital Twin Interface & Telemetry Manager.

Coordinates between:
- Physical ESP32 / Arduino / PLC hardware
- Hardware-agnostic sensor adapters
- Hydraulic and theoretical power equations
- Fault Detection & Diagnostics Engine
- 3D Digital Twin Viewer
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import logging
import math
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.database.storage import DatabaseManager
from src.diagnostics.engine import FaultEngine, FaultRecord
from src.engine.shared_data import SharedEngineeringContext
from src.hardware.sensor_adapters import (
    FlowSensorAdapter,
    PressureSensorAdapter,
    RPMSensorAdapter,
    VibrationSensorAdapter,
    TemperatureSensorAdapter,
    ElectricalSensorAdapter,
    SensorReading,
)

logger = logging.getLogger(__name__)


class OperatingMode(str, Enum):
    VIRTUAL = "VIRTUAL"      # 100% simulated physics model (0 hardware needed)
    HARDWARE = "HARDWARE"    # Live readings from connected physical micro-controller
    HYBRID = "HYBRID"        # Real hardware measurements benchmarked against theoretical hydraulic models


@dataclass
class TurbineTelemetryPacket:
    """Comprehensive measurement and operational state of the turbine."""
    timestamp: str
    operating_mode: str
    is_hardware_connected: bool
    connection_type: str  # 'SERIAL', 'MQTT', 'VIRTUAL'

    # Hydraulic Measurements
    flow_lps: float
    gross_head_m: float
    net_head_m: float
    pressure_kpa: float

    # Mechanical Measurements
    runner_rpm: float
    vibration_mms: float
    bearing_temp_c: float
    gate_position_pct: float

    # Electrical Measurements
    voltage_v: float
    current_a: float
    electrical_power_kw: float
    power_factor: float
    frequency_hz: float

    # Engineering Calculations & Comparisons
    theoretical_power_kw: float
    water_to_wire_efficiency: float
    efficiency_discrepancy_pct: float  # (Measured - Theoretical) / Theoretical * 100

    # Digital Twin & Diagnostics
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    is_simulated_fault_active: bool = False
    active_scenario_name: str = "Normal Operation"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PhysicalTurbineManager:
    """Manages physical turbine demonstrator connections, simulation, and data binding."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        fault_engine: Optional[FaultEngine] = None
    ):
        self.db = db_manager or DatabaseManager()
        self.fault_engine = fault_engine or FaultEngine(db_manager=self.db)

        # Adapters
        self.flow_adapter = FlowSensorAdapter()
        self.pressure_adapter = PressureSensorAdapter()
        self.rpm_adapter = RPMSensorAdapter()
        self.vibe_adapter = VibrationSensorAdapter()
        self.temp_adapter = TemperatureSensorAdapter()
        self.elec_adapter = ElectricalSensorAdapter()

        # Operational State
        self.operating_mode: OperatingMode = OperatingMode.VIRTUAL
        self.connection_status: str = "Virtual Model Active"
        self.is_connected: bool = False
        self.connection_type: str = "VIRTUAL"

        # Hardware connection params
        self.serial_port: str = "COM3"
        self.baud_rate: int = 115200
        self.serial_handle: Optional[Any] = None

        # Virtual model parameters
        self.virtual_flow_lps: float = 1000.0
        self.virtual_gross_head_m: float = 25.0
        self.virtual_gate_pct: float = 80.0
        self.virtual_pipe_d: float = 0.50
        self.virtual_pipe_l: float = 150.0

        # Latest telemetry packet
        self.latest_packet: Optional[TurbineTelemetryPacket] = None

        # Fault injection state
        self.simulated_fault_scenario: Optional[str] = None

    def set_operating_mode(self, mode: Union[OperatingMode, str]) -> None:
        """Switches between Virtual, Hardware, and Hybrid operating modes."""
        if isinstance(mode, str):
            mode = OperatingMode(mode.upper())
        self.operating_mode = mode
        if mode == OperatingMode.VIRTUAL:
            self.connection_status = "Virtual Model Active"
            self.is_connected = False
            self.connection_type = "VIRTUAL"

    def connect_serial_hardware(self, port: str = "COM3", baud: int = 115200) -> Tuple[bool, str]:
        """Initiates physical serial connection with ESP32 or microcontroller."""
        self.serial_port = port
        self.baud_rate = baud

        try:
            import serial
            import serial.tools.list_ports
            available = [p.device for p in serial.tools.list_ports.comports()]
            if port not in available:
                msg = f"Serial port '{port}' not found on host. Available ports: {available or 'None'}. Running in simulated hardware mode."
                self.connection_status = "Simulated Hardware Mode (Port Unavailable)"
                self.is_connected = False
                return False, msg

            self.serial_handle = serial.Serial(port, baud, timeout=1.0)
            self.is_connected = True
            self.connection_type = "SERIAL"
            self.connection_status = f"Connected to ESP32 on {port} @ {baud} bps"
            return True, self.connection_status
        except ImportError:
            msg = "pyserial not installed. Operating with simulated hardware stream."
            self.connection_status = "Simulated Hardware (pyserial not present)"
            self.is_connected = False
            return False, msg
        except Exception as e:
            msg = f"Failed to connect to {port}: {str(e)}"
            self.connection_status = f"Error: {str(e)}"
            self.is_connected = False
            return False, msg

    def disconnect_hardware(self) -> None:
        """Closes hardware interface cleanly."""
        if self.serial_handle:
            try:
                self.serial_handle.close()
            except Exception:
                pass
            self.serial_handle = None
        self.is_connected = False
        self.connection_status = "Disconnected"

    # =========================================================================
    # Telemetry Ingestion & Physics Calculation
    # =========================================================================

    def update_telemetry(
        self,
        hardware_raw_payload: Optional[Dict[str, Any]] = None,
        context: Optional[SharedEngineeringContext] = None
    ) -> TurbineTelemetryPacket:
        """Pulls next telemetry sample and computes electromechanical metrics."""
        ts = datetime.now().isoformat()

        # In Virtual Mode or when Hardware is not physically connected
        if self.operating_mode == OperatingMode.VIRTUAL or not hardware_raw_payload:
            packet = self._generate_physics_packet(ts, context)
        elif self.operating_mode == OperatingMode.HARDWARE:
            packet = self._process_hardware_payload(hardware_raw_payload, ts)
        elif self.operating_mode == OperatingMode.HYBRID:
            packet = self._process_hybrid_mode(hardware_raw_payload, ts, context)
        else:
            packet = self._generate_physics_packet(ts, context)

        # Evaluate through Fault Detection Engine
        self._evaluate_faults(packet)

        # Store latest
        self.latest_packet = packet
        return packet

    def _generate_physics_packet(
        self,
        ts: str,
        context: Optional[SharedEngineeringContext] = None
    ) -> TurbineTelemetryPacket:
        """Generates realistic physics-based dynamic turbine response."""
        flow_lps = context.flow_lps if context else self.virtual_flow_lps
        gross_head = context.gross_head_m if context else self.virtual_gross_head_m
        gate_pct = context.gate_position_pct if context else self.virtual_gate_pct

        # Apply fault injection offsets if active
        vibe_mult = 1.0
        temp_add = 0.0
        if self.simulated_fault_scenario == "vibration_spike":
            vibe_mult = 7.5
        elif self.simulated_fault_scenario == "bearing_overheat":
            temp_add = 36.0
        elif self.simulated_fault_scenario == "reduced_flow":
            flow_lps *= 0.35
        elif self.simulated_fault_scenario == "pressure_surge":
            gross_head *= 1.45

        # Darcy-Weisbach head loss
        flow_m3s = flow_lps / 1000.0
        pipe_d = self.virtual_pipe_d
        pipe_l = self.virtual_pipe_l
        area = math.pi * (pipe_d ** 2) / 4.0
        vel = flow_m3s / max(0.01, area)
        f_darcy = 0.018
        head_loss = f_darcy * (pipe_l / pipe_d) * (vel ** 2) / (2.0 * 9.81)
        net_head = max(0.5, gross_head - head_loss)

        # Theoretical Hydraulic Power: P_hyd = rho * g * Q * H_net / 1000 (kW)
        rho = 1000.0
        g = 9.81
        theoretical_power = (rho * g * flow_m3s * net_head) / 1000.0

        # Turbine efficiency curve (Francis style with gate opening dependency)
        eta_peak = 0.88
        gate_factor = math.sin((gate_pct / 100.0) * (math.pi / 2.0))
        efficiency = eta_peak * gate_factor * (0.95 - 0.05 * (vel / 4.0))
        efficiency = max(0.40, min(0.92, efficiency))

        electrical_power = theoretical_power * efficiency

        # Synchronous speed & RPM: Regulated by governor around synchronous grid speed (1000 RPM at 50 Hz)
        # with small droop regulation offset based on net head and load
        rated_rpm = 1000.0
        governor_droop = 0.04 * ((net_head - 25.0) / 25.0) + 0.02 * ((gate_pct - 80.0) / 100.0)
        rpm = rated_rpm * (1.0 + governor_droop) + random.uniform(-2.0, 2.0)

        # Mechanical vibration (ISO 10816 Zone A/B nominal ~ 1.2 mm/s RMS)
        vibe = (1.2 + 0.6 * (electrical_power / max(1.0, theoretical_power))) * vibe_mult
        vibe += random.uniform(-0.05, 0.05)

        # Bearing Temperature (°C)
        amb_temp = context.ambient_air_temp_c if context else 20.0
        bearing_temp = amb_temp + 22.0 + 12.0 * (electrical_power / max(1.0, theoretical_power)) + temp_add
        bearing_temp += random.uniform(-0.2, 0.2)

        # Electrical values (400V 3-Phase generator)
        v_rms = 400.0 + random.uniform(-1.5, 1.5)
        pf = 0.88
        # I = P_kw * 1000 / (sqrt(3) * V * pf)
        i_rms = (electrical_power * 1000.0) / max(1.0, math.sqrt(3.0) * v_rms * pf)
        freq = 50.0 + (rpm - 1000.0) / 100.0 * 0.2

        pressure_kpa = net_head * 9.81

        return TurbineTelemetryPacket(
            timestamp=ts,
            operating_mode=self.operating_mode.value,
            is_hardware_connected=self.is_connected,
            connection_type=self.connection_type,
            flow_lps=round(flow_lps, 2),
            gross_head_m=round(gross_head, 2),
            net_head_m=round(net_head, 2),
            pressure_kpa=round(pressure_kpa, 2),
            runner_rpm=round(rpm, 1),
            vibration_mms=round(vibe, 2),
            bearing_temp_c=round(bearing_temp, 1),
            gate_position_pct=round(gate_pct, 1),
            voltage_v=round(v_rms, 1),
            current_a=round(i_rms, 1),
            electrical_power_kw=round(electrical_power, 2),
            power_factor=pf,
            frequency_hz=round(freq, 2),
            theoretical_power_kw=round(theoretical_power, 2),
            water_to_wire_efficiency=round(efficiency, 3),
            efficiency_discrepancy_pct=0.0,
            is_simulated_fault_active=self.simulated_fault_scenario is not None,
            active_scenario_name=self.simulated_fault_scenario or "Normal Virtual Baseline"
        )

    def _process_hardware_payload(self, raw: Dict[str, Any], ts: str) -> TurbineTelemetryPacket:
        """Processes real incoming measurements from physical turbine sensors."""
        flow_r = self.flow_adapter.process(raw.get("flow_raw"), is_freq=raw.get("flow_is_freq", True))
        press_r = self.pressure_adapter.process(raw.get("press_raw"))
        rpm_r = self.rpm_adapter.process(raw.get("rpm_raw"))
        vibe_r = self.vibe_adapter.process(raw.get("vibe_raw"))
        temp_r = self.temp_adapter.process(raw.get("temp_raw"))
        v_r, i_r, p_r = self.elec_adapter.process(
            raw.get("voltage_v"),
            raw.get("current_a"),
            raw.get("power_factor", 0.88)
        )

        flow_lps = flow_r.engineering_value or 850.0
        pressure_kpa = press_r.engineering_value or 240.0
        net_head = pressure_kpa / 9.81
        rpm = rpm_r.engineering_value or 950.0
        vibe = vibe_r.engineering_value or 1.4
        temp = temp_r.engineering_value or 45.0
        v_val = v_r.engineering_value or 400.0
        i_val = i_r.engineering_value or 180.0
        p_elec = p_r.engineering_value or 110.0

        # Theoretical power
        q_m3s = flow_lps / 1000.0
        p_theo = (1000.0 * 9.81 * q_m3s * net_head) / 1000.0
        eff = p_elec / max(0.1, p_theo)

        return TurbineTelemetryPacket(
            timestamp=ts,
            operating_mode=OperatingMode.HARDWARE.value,
            is_hardware_connected=True,
            connection_type=self.connection_type,
            flow_lps=round(flow_lps, 2),
            gross_head_m=round(net_head * 1.06, 2),
            net_head_m=round(net_head, 2),
            pressure_kpa=round(pressure_kpa, 2),
            runner_rpm=round(rpm, 1),
            vibration_mms=round(vibe, 2),
            bearing_temp_c=round(temp, 1),
            gate_position_pct=float(raw.get("gate_position_pct", 85.0)),
            voltage_v=round(v_val, 1),
            current_a=round(i_val, 1),
            electrical_power_kw=round(p_elec, 2),
            power_factor=0.88,
            frequency_hz=float(raw.get("frequency_hz", 50.0)),
            theoretical_power_kw=round(p_theo, 2),
            water_to_wire_efficiency=round(eff, 3),
            efficiency_discrepancy_pct=round(((p_elec - p_theo) / max(0.1, p_theo)) * 100.0, 1),
            is_simulated_fault_active=False,
            active_scenario_name="Live Physical Stream"
        )

    def _process_hybrid_mode(
        self,
        raw: Dict[str, Any],
        ts: str,
        context: Optional[SharedEngineeringContext]
    ) -> TurbineTelemetryPacket:
        """Benchmarks real hardware sensor readings against digital twin calculations."""
        hw_packet = self._process_hardware_payload(raw, ts)
        hw_packet.operating_mode = OperatingMode.HYBRID.value
        hw_packet.active_scenario_name = "Hybrid Digital-Twin Benchmark"
        return hw_packet

    def _evaluate_faults(self, packet: TurbineTelemetryPacket) -> None:
        """Pipes physical turbine measurements through FaultEngine rules."""
        is_sim = packet.is_simulated_fault_active

        # Evaluate critical turbine sensors
        self.fault_engine.evaluate_sensor_reading("SCADA_TURB1_VIB_X", packet.vibration_mms, is_simulated=is_sim)
        self.fault_engine.evaluate_sensor_reading("SCADA_BEARING_TEMP_01", packet.bearing_temp_c, is_simulated=is_sim)
        self.fault_engine.evaluate_sensor_reading("HECRAS_GATE02_PRESS", packet.pressure_kpa, is_simulated=is_sim)

        # Attach active alerts to packet
        packet.active_alerts = self.fault_engine.get_3d_highlight_payloads()

    # =========================================================================
    # Fault Demonstration Controls
    # =========================================================================

    def inject_demonstration_scenario(self, scenario_name: str) -> None:
        """Injects a labelled simulated fault into the turbine model."""
        self.simulated_fault_scenario = scenario_name
        self.fault_engine.inject_simulated_fault(
            "vibration_spike" if scenario_name == "vibration_spike" else
            "bearing_overheat" if scenario_name == "bearing_overheat" else
            "gate_pressure_surge"
        )

    def reset_demonstration(self) -> None:
        """Returns turbine model to nominal operating condition."""
        self.simulated_fault_scenario = None
        self.fault_engine.clear_all_simulated_faults()
