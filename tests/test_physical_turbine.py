"""Unit tests for Physical Hydropower Turbine Interface and Sensor Adapters."""

import pytest

from src.hardware.sensor_adapters import (
    FlowSensorAdapter,
    PressureSensorAdapter,
    RPMSensorAdapter,
    VibrationSensorAdapter,
    TemperatureSensorAdapter,
    ElectricalSensorAdapter,
    SensorReading,
)
from src.hardware.turbine_interface import (
    OperatingMode,
    TurbineTelemetryPacket,
    PhysicalTurbineManager,
)


def test_sensor_adapters_nominal_and_edge_cases():
    """Tests engineering conversion and edge-case handling for physical sensor signals."""
    # 1. Flow Sensor
    flow_adapt = FlowSensorAdapter(pulses_per_liter=5.0)
    res_flow = flow_adapt.process(raw_input=500.0, is_freq=True)
    assert res_flow.status == "OK"
    assert res_flow.engineering_value == 100.0  # 500 / 5.0 = 100 L/s

    # Missing flow sensor
    res_missing = flow_adapt.process(raw_input=None)
    assert res_missing.status == "MISSING"
    assert res_missing.engineering_value is None

    # 2. Pressure Sensor (0.5V - 4.5V ratiometric)
    press_adapt = PressureSensorAdapter(max_pressure_kpa=1000.0)
    res_press = press_adapt.process(volts=2.5)  # Midpoint: (2.5 - 0.5) / 4.0 = 0.5 -> 500 kPa
    assert res_press.status == "OK"
    assert pytest.approx(res_press.engineering_value, 0.1) == 500.0

    # Disconnected wire (< 0.2V)
    res_disc = press_adapt.process(volts=0.05)
    assert res_disc.status == "DISCONNECTED"

    # 3. RPM Sensor
    rpm_adapt = RPMSensorAdapter(pulses_per_rev=2)
    res_rpm = rpm_adapt.process(pulse_freq_hz=33.33)
    assert res_rpm.status == "OK"
    assert pytest.approx(res_rpm.engineering_value, 1.0) == 1000.0

    # 4. Temperature Sensor (1-Wire)
    temp_adapt = TemperatureSensorAdapter()
    res_temp = temp_adapt.process(deg_c=48.5)
    assert res_temp.status == "OK"
    assert res_temp.engineering_value == 48.5

    # Power-on bus disconnected error (-127°C)
    res_temp_err = temp_adapt.process(deg_c=-127.0)
    assert res_temp_err.status == "DISCONNECTED"

    # 5. Electrical 3-Phase Meter Adapter: P = sqrt(3) * V * I * pf / 1000
    elec_adapt = ElectricalSensorAdapter(is_three_phase=True, default_power_factor=0.88)
    v_r, i_r, p_r = elec_adapt.process(voltage_v=400.0, current_a=250.0, power_factor=0.88)
    assert v_r.status == "OK"
    assert i_r.status == "OK"
    assert p_r.status == "OK"
    # P = sqrt(3) * 400 * 250 * 0.88 / 1000 = 152.42 kW
    assert pytest.approx(p_r.engineering_value, 0.5) == 152.42


def test_virtual_operating_mode():
    """Verifies that Virtual Mode calculates dynamic physical turbine metrics without hardware."""
    manager = PhysicalTurbineManager()
    manager.set_operating_mode(OperatingMode.VIRTUAL)

    packet = manager.update_telemetry()
    assert packet.operating_mode == "VIRTUAL"
    assert packet.flow_lps > 0
    assert packet.net_head_m > 0
    assert packet.theoretical_power_kw > 0
    assert packet.electrical_power_kw > 0
    assert packet.water_to_wire_efficiency > 0.5
    assert 900.0 <= packet.runner_rpm <= 1100.0
    assert packet.voltage_v > 380.0
    assert packet.current_a > 0
    assert packet.is_simulated_fault_active is False


def test_fault_demonstration_mode():
    """Verifies fault injection and single-click reset in Physical Turbine Lab."""
    manager = PhysicalTurbineManager()

    # Inject vibration spike
    manager.inject_demonstration_scenario("vibration_spike")
    packet = manager.update_telemetry()

    assert packet.is_simulated_fault_active is True
    assert packet.vibration_mms > 8.0  # Elevated vibration
    assert len(packet.active_alerts) >= 1
    assert any("SCADA_TURB1_VIB_X" in a.get("sensor_id", "") for a in packet.active_alerts)

    # Reset demonstration
    manager.reset_demonstration()
    packet_reset = manager.update_telemetry()
    assert packet_reset.is_simulated_fault_active is False
    assert packet_reset.vibration_mms < 4.0
    assert len(packet_reset.active_alerts) == 0


def test_hybrid_mode_comparison():
    """Verifies Hybrid Mode comparing hardware measurements against theoretical hydraulics."""
    manager = PhysicalTurbineManager()
    manager.set_operating_mode(OperatingMode.HYBRID)

    raw_hw = {
        "flow_raw": 1000.0,
        "flow_is_freq": False,
        "press_raw": 1.5,
        "rpm_raw": 33.3,
        "vibe_raw": 0.05,
        "temp_raw": 42.0,
        "voltage_v": 400.0,
        "current_a": 200.0,
        "power_factor": 0.88,
        "gate_position_pct": 80.0
    }
    packet = manager.update_telemetry(hardware_raw_payload=raw_hw)
    assert packet.operating_mode == "HYBRID"
    assert packet.electrical_power_kw > 0
    assert packet.theoretical_power_kw > 0
    assert isinstance(packet.efficiency_discrepancy_pct, float)
