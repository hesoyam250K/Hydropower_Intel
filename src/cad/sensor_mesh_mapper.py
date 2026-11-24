"""Sensor to 3D Mesh Mapping System for Hydropower Intelligence.

Binds SCADA tags, IoT sensors, and hydraulic simulation nodes to 3D components:
- SCADA_TURB1_VIB_X -> turbine_runner (or Turbine_01_MainShaft)
- HECRAS_GATE02_PRESS -> intake_gate (or Spillway_Gate_02)
- IOT_DAM_CRACK_09 -> dam_structure (or Dam_Wall_Section_B)
- SCADA_BEARING_TEMP_01 -> generator_stator
- IOT_PENSTOCK_SURGE_01 -> penstock_pipe
- IOT_BRIDGE_STRESS_01 -> thermal_bridge_regions
- IOT_JOINT_TRAVEL_01 -> expansion_joints
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAP_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sensor_mesh_map.json"


class SensorMeshMapper:
    """Manages O(1) resolution between physical sensor tags and 3D digital-twin sub-components."""

    DEFAULT_MAPPINGS: Dict[str, Dict[str, Any]] = {
        "SCADA_TURB1_VIB_X": {
            "component_id": "turbine_runner",
            "aliases": ["Turbine_01_MainShaft", "turbine_runner", "Turbine_Rotor_STEP"],
            "metric": "Shaft Vibration",
            "unit": "mm/s",
            "warning_threshold": 4.5,
            "critical_threshold": 8.5,
            "comparison": ">",
            "subsystem": "Turbine Runner & Shaft"
        },
        "HECRAS_GATE02_PRESS": {
            "component_id": "intake_gate",
            "aliases": ["Spillway_Gate_02", "intake_gate", "Intake_Sluice_Gate"],
            "metric": "Hydrostatic Pressure",
            "unit": "kPa",
            "warning_threshold": 380.0,
            "critical_threshold": 450.0,
            "comparison": ">",
            "subsystem": "Intake & Spillway Headgate"
        },
        "IOT_DAM_CRACK_09": {
            "component_id": "dam_structure",
            "aliases": ["Dam_Wall_Section_B", "dam_structure", "Concrete_Dam"],
            "metric": "Concrete Displacement",
            "unit": "mm",
            "warning_threshold": 1.2,
            "critical_threshold": 2.0,
            "comparison": ">",
            "subsystem": "Concrete Gravity Dam Crest"
        },
        "SCADA_BEARING_TEMP_01": {
            "component_id": "generator_stator",
            "aliases": ["generator_stator", "Generator_Main_Bearing"],
            "metric": "Bearing Temperature",
            "unit": "°C",
            "warning_threshold": 65.0,
            "critical_threshold": 75.0,
            "comparison": ">",
            "subsystem": "Synchronous Generator"
        },
        "IOT_PENSTOCK_SURGE_01": {
            "component_id": "penstock_pipe",
            "aliases": ["penstock_pipe", "High_Pressure_Penstock"],
            "metric": "Transient Pressure",
            "unit": "bar",
            "warning_threshold": 18.0,
            "critical_threshold": 22.0,
            "comparison": ">",
            "subsystem": "Penstock Conduit"
        },
        "IOT_BRIDGE_STRESS_01": {
            "component_id": "thermal_bridge_regions",
            "aliases": ["thermal_bridge_regions", "Bridge_Pier_Saddles"],
            "metric": "Restrained Thermal Stress",
            "unit": "MPa",
            "warning_threshold": 20.0,
            "critical_threshold": 30.0,
            "comparison": ">",
            "subsystem": "Hydrothermal Bridge Saddles"
        },
        "IOT_JOINT_TRAVEL_01": {
            "component_id": "expansion_joints",
            "aliases": ["expansion_joints", "Bridge_Modular_Joint"],
            "metric": "Joint Travel",
            "unit": "mm",
            "warning_threshold": 30.0,
            "critical_threshold": 45.0,
            "comparison": ">",
            "subsystem": "Elastomeric Expansion Joints"
        },
        "IOT_TURBINE_RPM_01": {
            "component_id": "turbine_runner",
            "aliases": ["turbine_runner", "Turbine_Rotor_STEP"],
            "metric": "Runner Speed",
            "unit": "RPM",
            "warning_threshold": 1200.0,
            "critical_threshold": 1450.0,
            "comparison": ">",
            "subsystem": "Turbine Runner"
        }
    }

    def __init__(self, mapping_file: Optional[Path] = None):
        self.mapping_file = mapping_file or DEFAULT_MAP_PATH
        self.mappings: Dict[str, Dict[str, Any]] = {}
        self.load_mappings()

    def load_mappings(self) -> None:
        """Loads mappings from JSON file or initializes defaults."""
        if self.mapping_file.exists():
            try:
                with open(self.mapping_file, "r", encoding="utf-8") as f:
                    self.mappings = json.load(f)
            except Exception:
                self.mappings = dict(self.DEFAULT_MAPPINGS)
        else:
            self.mappings = dict(self.DEFAULT_MAPPINGS)
            self.save_mappings()

    def save_mappings(self) -> None:
        """Persists sensor mappings to local JSON file."""
        self.mapping_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.mapping_file, "w", encoding="utf-8") as f:
            json.dump(self.mappings, f, indent=2)

    def get_component_id(self, sensor_id: str) -> Optional[str]:
        """Resolves sensor tag to primary 3D component identifier."""
        data = self.mappings.get(sensor_id)
        return data.get("component_id") if data else None

    def get_aliases_for_component(self, component_id: str) -> List[str]:
        """Returns all recognized mesh name aliases for a component."""
        aliases = [component_id]
        for data in self.mappings.values():
            if data.get("component_id") == component_id:
                for a in data.get("aliases", []):
                    if a not in aliases:
                        aliases.append(a)
        return aliases

    def resolve_mesh_name(self, target: str, available_mesh_names: List[str]) -> Optional[str]:
        """Matches a target sensor ID, component ID, or alias against actual loaded 3D scene mesh names."""
        # 1. If target is a sensor_id, resolve its component and aliases
        target_keys = [target]
        if target in self.mappings:
            comp_id = self.mappings[target].get("component_id", "")
            if comp_id:
                target_keys.append(comp_id)
            for a in self.mappings[target].get("aliases", []):
                if a not in target_keys:
                    target_keys.append(a)
        else:
            for a in self.get_aliases_for_component(target):
                if a not in target_keys:
                    target_keys.append(a)

        # 2. Check exact and case-insensitive match for each target key
        for key in target_keys:
            if key in available_mesh_names:
                return key
            key_norm = key.lower().replace("_", "").replace("-", "")
            for m in available_mesh_names:
                if m.lower().replace("_", "").replace("-", "") == key_norm:
                    return m

        # 3. Substring matching
        for key in target_keys:
            key_norm = key.lower().replace("_", "").replace("-", "")
            for m in available_mesh_names:
                m_norm = m.lower().replace("_", "").replace("-", "")
                if key_norm in m_norm or m_norm in key_norm:
                    return m

        return None

    def add_or_update_mapping(
        self,
        sensor_id: str,
        component_id: str,
        metric: str,
        unit: str,
        warning_threshold: float,
        critical_threshold: float,
        aliases: Optional[List[str]] = None,
        subsystem: str = ""
    ) -> None:
        """Adds or updates a sensor-to-component configuration."""
        self.mappings[sensor_id] = {
            "component_id": component_id,
            "aliases": aliases or [component_id],
            "metric": metric,
            "unit": unit,
            "warning_threshold": float(warning_threshold),
            "critical_threshold": float(critical_threshold),
            "comparison": ">",
            "subsystem": subsystem or component_id
        }
        self.save_mappings()
