"""MQTT physical sensor integration layer for ESP32 and industrial PLCs.

Features:
- Connects to local or LAN MQTT brokers (e.g. Mosquitto) without cloud dependency.
- Parses incoming JSON telemetry from flow meters, pressure transmitters, and power meters.
- Thread-safe packet buffering for the Streamlit dashboard.
- Clear connection state management and error diagnostics.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

from src.telemetry.sensor_manager import (
    TelemetryDataPoint,
    TelemetryThresholds,
    evaluate_telemetry_point,
)

logger = logging.getLogger(__name__)


@dataclass
class MQTTConfig:
    """MQTT connection parameters."""
    broker_host: str = "localhost"
    broker_port: int = 1883
    topic: str = "hydropower/telemetry/#"
    client_id: str = "HydroPower_Intelligence_Client"
    username: Optional[str] = None
    password: Optional[str] = None
    keepalive: int = 60


class HydroMQTTClient:
    """Manages asynchronous MQTT connection and sensor packet ingestion."""

    def __init__(
        self,
        config: Optional[MQTTConfig] = None,
        on_data_callback: Optional[Callable[[TelemetryDataPoint], None]] = None
    ):
        self.config = config or MQTTConfig()
        self.on_data_callback = on_data_callback

        self.client: Optional[Any] = None
        self.is_connected: bool = False
        self.status_message: str = "Disconnected"
        self.last_packet_time: Optional[str] = None
        self.packet_count: int = 0
        self.latest_data: Optional[TelemetryDataPoint] = None

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def connect_async(self) -> None:
        """Starts connection attempt in background thread to prevent UI freezing."""
        if not PAHO_AVAILABLE:
            self.status_message = "paho-mqtt library not installed."
            return

        if self.is_connected:
            return

        self.status_message = f"Connecting to {self.config.broker_host}:{self.config.broker_port}..."
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()

    def _run_client(self) -> None:
        """Internal client execution thread."""
        try:
            # Paho MQTT v2 compatibility
            try:
                self.client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=self.config.client_id
                )
            except AttributeError:
                self.client = mqtt.Client(client_id=self.config.client_id)

            if self.config.username:
                self.client.username_pw_set(self.config.username, self.config.password)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            self.client.connect(
                self.config.broker_host,
                self.config.broker_port,
                keepalive=self.config.keepalive
            )
            self.client.loop_start()

        except Exception as e:
            with self._lock:
                self.is_connected = False
                self.status_message = f"Connection failed: {str(e)}"
            logger.error("MQTT Connection error: %s", e)

    def disconnect(self) -> None:
        """Gracefully disconnects from broker."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        with self._lock:
            self.is_connected = False
            self.status_message = "Disconnected by user."

    def _on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        rc_code = rc.value if hasattr(rc, "value") else rc
        with self._lock:
            if rc_code == 0:
                self.is_connected = True
                self.status_message = f"Connected to {self.config.broker_host}:{self.config.broker_port}"
                client.subscribe(self.config.topic)
            else:
                self.is_connected = False
                self.status_message = f"Connection refused by broker (Code {rc_code})"

    def _on_disconnect(self, client, userdata, flags_or_rc, *args) -> None:
        with self._lock:
            self.is_connected = False
            self.status_message = "Disconnected from broker."

    def _on_message(self, client, userdata, msg) -> None:
        """Parses payload from ESP32 / PLC into TelemetryDataPoint."""
        try:
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)

            now_iso = datetime.now().isoformat()
            point = TelemetryDataPoint(
                timestamp=data.get("timestamp", now_iso),
                source="PHYSICAL_MQTT",
                flow_lps=float(data.get("flow_lps", data.get("flow", 0.0))),
                net_head_m=float(data.get("net_head_m", data.get("head_m", 0.0))),
                power_kw=float(data.get("power_kw", data.get("power", 0.0))),
                frequency_hz=float(data.get("frequency_hz", data.get("frequency", 50.0))),
                voltage_v=float(data.get("voltage_v", data.get("voltage", 400.0))),
                current_a=float(data.get("current_a", data.get("current", 0.0))),
                gate_position_pct=float(data.get("gate_pct", data.get("gate", 80.0))),
                bearing_temp_c=float(data.get("bearing_temp_c", data.get("temp", 45.0))),
                vibration_mms=float(data.get("vibration_mms", data.get("vib", 1.2))),
            )

            evaluated = evaluate_telemetry_point(point)

            with self._lock:
                self.latest_data = evaluated
                self.packet_count += 1
                self.last_packet_time = now_iso

            if self.on_data_callback:
                self.on_data_callback(evaluated)

        except Exception as e:
            logger.warning("Failed to decode MQTT packet: %s", e)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_connected": self.is_connected,
                "status_message": self.status_message,
                "packet_count": self.packet_count,
                "last_packet_time": self.last_packet_time,
                "broker": f"{self.config.broker_host}:{self.config.broker_port}",
                "topic": self.config.topic,
            }
