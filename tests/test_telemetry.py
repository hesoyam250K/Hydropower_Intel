"""Unit tests for telemetry data generator, sensor thresholds, and MQTT parser."""

import pytest
from src.telemetry.sensor_manager import (
    TelemetryDataPoint,
    TelemetryThresholds,
    evaluate_telemetry_point,
)
from src.telemetry.simulated_data import SimulatedTelemetryGenerator
from src.telemetry.mqtt_client import HydroMQTTClient, MQTTConfig


def test_telemetry_threshold_evaluation():
    """Verifies that alarms trigger when physical boundaries are breached."""
    point = TelemetryDataPoint(
        timestamp="2026-01-01T12:00:00",
        source="SIMULATED",
        flow_lps=1000.0,
        net_head_m=30.0,
        power_kw=250.0,
        frequency_hz=52.5,  # Too high (> 50.5 Hz)
        voltage_v=400.0,
        current_a=360.0,
        gate_position_pct=80.0,
        bearing_temp_c=78.0,  # Too high (> 70 C)
        vibration_mms=5.2,  # Too high (> 4.5 mm/s)
    )

    evaluated = evaluate_telemetry_point(point)
    assert evaluated.status_level == "ALARM"
    assert len(evaluated.alerts) >= 2


def test_simulated_telemetry_generator():
    """Verifies that simulated generator produces consistent data tagged as SIMULATED."""
    gen = SimulatedTelemetryGenerator(base_flow_lps=1000.0, base_head_m=25.0)
    pt1 = gen.generate_next_point()

    assert pt1.source == "SIMULATED"
    assert pt1.flow_lps > 500.0
    assert pt1.power_kw > 0.0
    assert 48.0 < pt1.frequency_hz < 52.0

    # Test disturbance injection
    gen.trigger_disturbance("bearing_fault", True)
    pt2 = gen.generate_next_point()
    assert pt2.bearing_temp_c > pt1.bearing_temp_c


def test_mqtt_client_initialization():
    """Verifies MQTT client structure and disconnection state."""
    cfg = MQTTConfig(broker_host="127.0.0.1", broker_port=1883)
    client = HydroMQTTClient(config=cfg)
    status = client.get_status()

    assert status["is_connected"] is False
    assert status["broker"] == "127.0.0.1:1883"
    assert status["packet_count"] == 0
