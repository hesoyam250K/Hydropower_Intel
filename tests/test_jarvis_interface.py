"""Unit tests for JARVIS 3D HUD & Holographic AR Viewport."""

import pytest
from unittest.mock import patch

from src.components.jarvis_viewer import render_jarvis_viewer, load_local_js
from src.components.three_viewer import render_threejs_viewer, render_peppers_ghost_hologram
from src.engine.shared_data import SharedEngineeringContext
from src.geometry.mesh_builder import PlantGeometryBuilder


def test_local_offline_js_assets_exist():
    """Verifies Three.js, OrbitControls, and GLTFLoader are bundled locally."""
    three = load_local_js("three.min.js")
    controls = load_local_js("OrbitControls.js")
    gltf = load_local_js("GLTFLoader.js")

    assert len(three) > 1000
    assert len(controls) > 500
    assert len(gltf) > 500


def test_jarvis_viewer_html_generation():
    """Verifies that render_jarvis_viewer constructs complete HUD, commands, and AR elements."""
    ctx = SharedEngineeringContext(
        flow_lps=1250.0,
        gross_head_m=35.0,
        net_head_m=32.8,
        electrical_power_kw=320.0,
        runner_speed_rpm=1000.0
    )
    faults = [{
        "sensor_id": "SCADA_TURB1_VIB_X",
        "component_id": "turbine_runner",
        "severity": "CRITICAL",
        "fault_type": "DETECTED",
        "color_hex": "#ff2244",
        "message": "Shaft vibration limit breached: 9.4 mm/s"
    }]

    captured_html = []

    def mock_html(code, height=None, scrolling=False):
        captured_html.append(code)

    with patch("streamlit.components.v1.html", side_effect=mock_html):
        render_jarvis_viewer(
            context=ctx,
            fault_payloads=faults,
            mode="FLOW",
            height=700
        )

    assert len(captured_html) == 1
    html = captured_html[0]

    # Verify HUD features
    assert "--hud-color" in html
    assert "JARVIS 3D TWIN" in html
    assert "320.0 kW" in html
    assert "SCADA_TURB1_VIB_X" in html
    assert "#ff2244" in html

    # Verify Command and AR Handlers
    assert "toggleVoiceRecognition" in html
    assert "sendCommand" in html
    assert "toggleXRay" in html
    assert "toggleExploded" in html
    assert "toggleCutaway" in html
    assert "toggleARMode" in html
    assert "ar-camera-feed" in html


def test_peppers_ghost_preserved():
    """Verifies Pepper's Ghost 4-view pyramid hologram mode remains intact."""
    ctx = SharedEngineeringContext()
    captured_html = []

    def mock_html(code, height=None, scrolling=False):
        captured_html.append(code)

    with patch("streamlit.components.v1.html", side_effect=mock_html):
        render_peppers_ghost_hologram(context=ctx, height=700)

    assert len(captured_html) == 1
    assert "PEPPER'S GHOST 4-VIEW PYRAMID" in captured_html[0]
    assert "pyramid-apex-marker" in captured_html[0]
