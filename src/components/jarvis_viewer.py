"""JARVIS-Style 3D Engineering Interface & Holographic AR Viewport.

Integrates:
1. Full-screen interactive WebGL 3D engineering viewport
2. Translucent sci-fi engineering HUD overlay with dynamic color theme (--hud-color)
3. Raycasting component selection and engineering metadata inspection
4. Component isolation and X-ray wireframe inspection
5. Exploded component view and section cutaway slicing
6. Animated water streamlines and turbine runner rotation
7. Fault detection highlighting with pulsing emissive glow and camera fly-to
8. Local voice and text command parser (Web Speech API + offline text console)
9. Camera-based Augmented Reality (WebAR / camera passthrough)
10. Synchronized with hydraulic, hydrothermal, and physical sensor telemetry
"""

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st

from src.geometry.exporter import build_scene_and_export_glb
from src.geometry.mesh_builder import PlantGeometryBuilder
from src.engine.shared_data import SharedEngineeringContext

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "three"


def load_local_js(filename: str) -> str:
    """Reads locally bundled JavaScript file for 100% offline execution."""
    path = STATIC_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def render_jarvis_viewer(
    context: SharedEngineeringContext,
    builder: Optional[PlantGeometryBuilder] = None,
    custom_glb_bytes: Optional[bytes] = None,
    mode: str = "FLOW",
    model_filter: str = "BOTH",
    fault_payloads: Optional[List[Dict[str, Any]]] = None,
    height: int = 750
) -> None:
    """Renders the comprehensive JARVIS-style 3D Engineering HUD & AR Viewport."""

    # Generate GLB if custom bytes are not supplied
    if custom_glb_bytes:
        glb_bytes = custom_glb_bytes
    else:
        include_bridge = model_filter in ("BOTH", "BRIDGE_ONLY")
        actual_builder = builder or PlantGeometryBuilder(
            gross_head_m=context.gross_head_m,
            pipe_diameter_m=context.penstock_d if hasattr(context, "penstock_d") else 0.50,
            bridge_length_m=60.0,
            include_bridge=include_bridge
        )
        glb_bytes = build_scene_and_export_glb(builder=actual_builder, context=context, mode=mode)

    glb_b64 = base64.b64encode(glb_bytes).decode("utf-8")

    three_js = load_local_js("three.min.js")
    controls_js = load_local_js("OrbitControls.js")
    gltf_js = load_local_js("GLTFLoader.js")

    ctx_data = json.dumps(context.to_dict())
    active_faults_json = json.dumps(fault_payloads or context.active_faults or [])

    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            :root {{
                --hud-color: #00ffff;
                --hud-bg: rgba(11, 17, 32, 0.85);
                --hud-border: rgba(0, 255, 255, 0.35);
                --hud-text: #F8FAFC;
                --hud-muted: #94A3B8;
                --hud-alert: #ff2244;
                --hud-warn: #ffaa00;
            }}
            * {{
                box-sizing: border-box;
            }}
            body, html {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background-color: #070B14;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Courier New", monospace;
                color: var(--hud-text);
            }}
            #jarvis-container {{
                width: 100%;
                height: 100%;
                position: relative;
                overflow: hidden;
            }}
            /* AR Video Passthrough Background */
            #ar-camera-feed {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                object-fit: cover;
                z-index: 1;
                display: none;
            }}
            #webgl-canvas {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 2;
            }}
            /* Futuristic Corner Reticles */
            .hud-reticle {{
                position: absolute;
                width: 28px;
                height: 28px;
                border: 2px solid var(--hud-color);
                z-index: 10;
                pointer-events: none;
                opacity: 0.8;
            }}
            .reticle-tl {{ top: 10px; left: 10px; border-right: none; border-bottom: none; }}
            .reticle-tr {{ top: 10px; right: 10px; border-left: none; border-bottom: none; }}
            .reticle-bl {{ bottom: 10px; left: 10px; border-right: none; border-top: none; }}
            .reticle-br {{ bottom: 10px; right: 10px; border-left: none; border-top: none; }}

            /* Translucent HUD Header Panel */
            #hud-topbar {{
                position: absolute;
                top: 14px;
                left: 45px;
                right: 45px;
                z-index: 15;
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: var(--hud-bg);
                border: 1px solid var(--hud-border);
                border-radius: 6px;
                padding: 8px 16px;
                backdrop-filter: blur(8px);
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            }}
            .hud-brand {{
                display: flex;
                align-items: center;
                gap: 10px;
                font-weight: 800;
                letter-spacing: 1.5px;
                font-size: 13px;
                color: var(--hud-color);
                text-shadow: 0 0 10px var(--hud-color);
            }}
            .hud-status-badge {{
                font-size: 10px;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid var(--hud-color);
                color: var(--hud-color);
                letter-spacing: 1px;
                text-transform: uppercase;
                background: rgba(0, 255, 255, 0.08);
            }}
            /* Telemetry Top Bar Indicators */
            .telemetry-strip {{
                display: flex;
                gap: 16px;
                font-size: 11px;
            }}
            .telemetry-item {{
                display: flex;
                flex-direction: column;
            }}
            .telemetry-label {{
                font-size: 9px;
                color: var(--hud-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .telemetry-value {{
                font-weight: 700;
                color: var(--hud-text);
            }}

            /* Left HUD Sidebar: Component Inspector */
            #hud-left-panel {{
                position: absolute;
                top: 75px;
                left: 14px;
                width: 310px;
                z-index: 15;
                background: var(--hud-bg);
                border: 1px solid var(--hud-border);
                border-radius: 6px;
                padding: 12px 14px;
                backdrop-filter: blur(8px);
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            }}
            .panel-title {{
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1.2px;
                color: var(--hud-color);
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--hud-border);
                padding-bottom: 5px;
            }}
            #inspector-content {{
                font-size: 11px;
                line-height: 1.5;
            }}
            .meta-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 4px;
            }}
            .meta-k {{ color: var(--hud-muted); }}
            .meta-v {{ font-weight: 600; color: #FFF; }}

            /* Right HUD Sidebar: Faults & Event Stream */
            #hud-right-panel {{
                position: absolute;
                top: 75px;
                right: 14px;
                width: 320px;
                max-height: 380px;
                z-index: 15;
                background: var(--hud-bg);
                border: 1px solid var(--hud-border);
                border-radius: 6px;
                padding: 12px 14px;
                backdrop-filter: blur(8px);
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
                display: flex;
                flex-direction: column;
            }}
            #faults-list {{
                overflow-y: auto;
                max-height: 280px;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }}
            .fault-item {{
                background: rgba(30, 41, 59, 0.8);
                border-left: 3px solid var(--hud-alert);
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 10px;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .fault-item.warning {{
                border-left-color: var(--hud-warn);
            }}
            .fault-item:hover {{
                background: rgba(51, 65, 85, 0.9);
            }}
            .fault-title {{
                font-weight: 700;
                color: #FFF;
                display: flex;
                justify-content: space-between;
            }}

            /* Bottom Command & Control Deck */
            #hud-bottom-deck {{
                position: absolute;
                bottom: 14px;
                left: 45px;
                right: 45px;
                z-index: 15;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                background: var(--hud-bg);
                border: 1px solid var(--hud-border);
                border-radius: 6px;
                padding: 8px 14px;
                backdrop-filter: blur(8px);
            }}
            .deck-controls {{
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
                align-items: center;
            }}
            button.btn-hud {{
                background: rgba(30, 41, 59, 0.9);
                border: 1px solid var(--hud-border);
                color: var(--hud-text);
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 10.5px;
                font-weight: 700;
                letter-spacing: 0.5px;
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                gap: 4px;
            }}
            button.btn-hud:hover {{
                background: var(--hud-color);
                color: #070B14;
                box-shadow: 0 0 10px var(--hud-color);
            }}
            button.btn-hud.active {{
                background: var(--hud-color);
                color: #070B14;
            }}

            /* Voice & Text Console Box */
            #command-console {{
                display: flex;
                align-items: center;
                gap: 6px;
                flex: 1;
                max-width: 450px;
            }}
            #command-input {{
                background: rgba(15, 23, 42, 0.95);
                border: 1px solid var(--hud-border);
                border-radius: 4px;
                color: var(--hud-color);
                font-family: inherit;
                font-size: 11px;
                padding: 5px 10px;
                width: 100%;
                outline: none;
            }}
            #command-input:focus {{
                border-color: var(--hud-color);
                box-shadow: 0 0 8px var(--hud-border);
            }}
            #mic-btn {{
                background: rgba(30, 41, 59, 0.9);
                border: 1px solid var(--hud-border);
                color: var(--hud-color);
                padding: 5px 8px;
                border-radius: 4px;
                cursor: pointer;
            }}
            #mic-btn.listening {{
                background: var(--hud-alert);
                color: #FFF;
                animation: pulse-red 1s infinite;
            }}
            @keyframes pulse-red {{
                0% {{ box-shadow: 0 0 0 0 rgba(255, 34, 68, 0.7); }}
                70% {{ box-shadow: 0 0 0 8px rgba(255, 34, 68, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(255, 34, 68, 0); }}
            }}

            /* Theme Selector Pill */
            .theme-dots {{
                display: flex;
                gap: 5px;
                align-items: center;
            }}
            .theme-dot {{
                width: 13px;
                height: 13px;
                border-radius: 50%;
                cursor: pointer;
                border: 1px solid #FFF;
            }}
            .theme-cyan {{ background: #00ffff; }}
            .theme-gold {{ background: #ffbb00; }}
            .theme-red {{ background: #ff3355; }}
            .theme-purple {{ background: #b84dff; }}

            /* AR Notification Banner */
            #ar-notification {{
                position: absolute;
                top: 75px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 20;
                background: rgba(15, 23, 42, 0.95);
                border: 1px solid var(--hud-warn);
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
                color: #F8FAFC;
                display: none;
                backdrop-filter: blur(8px);
            }}
        </style>
    </head>
    <body>
        <div id="jarvis-container">
            <!-- Camera Feed for Mobile / Desktop WebAR Passthrough -->
            <video id="ar-camera-feed" autoplay playsinline muted></video>
            <div id="webgl-canvas"></div>

            <!-- Reticles -->
            <div class="hud-reticle reticle-tl"></div>
            <div class="hud-reticle reticle-tr"></div>
            <div class="hud-reticle reticle-bl"></div>
            <div class="hud-reticle reticle-br"></div>

            <!-- Topbar HUD -->
            <div id="hud-topbar">
                <div class="hud-brand">
                    <span>⚡ JARVIS 3D TWIN</span>
                    <span class="hud-status-badge" id="hud-mode-badge">{mode} MODE</span>
                </div>
                <div class="telemetry-strip">
                    <div class="telemetry-item">
                        <span class="telemetry-label">Water Flow</span>
                        <span class="telemetry-value" id="top-flow">{context.flow_lps:.1f} L/s</span>
                    </div>
                    <div class="telemetry-item">
                        <span class="telemetry-label">Net Head</span>
                        <span class="telemetry-value" id="top-head">{context.net_head_m:.1f} m</span>
                    </div>
                    <div class="telemetry-item">
                        <span class="telemetry-label">Electrical Power</span>
                        <span class="telemetry-value" style="color: #34D399;" id="top-power">{context.electrical_power_kw:.1f} kW</span>
                    </div>
                    <div class="telemetry-item">
                        <span class="telemetry-label">Frequency</span>
                        <span class="telemetry-value" id="top-freq">{context.frequency_hz:.2f} Hz</span>
                    </div>
                    <div class="telemetry-item">
                        <span class="telemetry-label">Runner RPM</span>
                        <span class="telemetry-value" id="top-rpm">{context.runner_speed_rpm:.0f} RPM</span>
                    </div>
                </div>
                <div class="theme-dots">
                    <span style="font-size: 9px; color: var(--hud-muted);">THEME</span>
                    <div class="theme-dot theme-cyan" onclick="setHUDTheme('cyan')"></div>
                    <div class="theme-dot theme-gold" onclick="setHUDTheme('gold')"></div>
                    <div class="theme-dot theme-red" onclick="setHUDTheme('red')"></div>
                    <div class="theme-dot theme-purple" onclick="setHUDTheme('purple')"></div>
                </div>
            </div>

            <!-- Left HUD: Component Inspection -->
            <div id="hud-left-panel">
                <div class="panel-title">
                    <span>COMPONENT TELEMETRY</span>
                    <span id="insp-badge" style="font-size: 9px; color: var(--hud-muted);">SELECT 3D MESH</span>
                </div>
                <div id="inspector-content">
                    <div style="color: var(--hud-muted); font-size: 10.5px;">
                        Click any 3D plant or bridge component to inspect engineering parameters and structural properties.
                    </div>
                </div>
            </div>

            <!-- Right HUD: Active Faults & Diagnostics -->
            <div id="hud-right-panel">
                <div class="panel-title">
                    <span>ACTIVE FAULTS & ANOMALIES</span>
                    <span id="fault-counter" style="color: var(--hud-alert); font-weight: 800;">0 ALERTS</span>
                </div>
                <div id="faults-list">
                    <div style="color: #64748B; font-size: 10px;">No critical faults detected. All systems nominal.</div>
                </div>
            </div>

            <!-- AR Notification -->
            <div id="ar-notification"></div>

            <!-- Bottom Control Deck -->
            <div id="hud-bottom-deck">
                <div class="deck-controls">
                    <button class="btn-hud" onclick="resetCamera()">⟲ Reset Camera</button>
                    <button class="btn-hud" id="btn-xray" onclick="toggleXRay()">⚡ X-Ray</button>
                    <button class="btn-hud" id="btn-explode" onclick="toggleExploded()">💥 Explode</button>
                    <button class="btn-hud" id="btn-cutaway" onclick="toggleCutaway()">✂ Section</button>
                    <button class="btn-hud" id="btn-flow" onclick="toggleFlowStreamlines()">🌊 Flow</button>
                    <button class="btn-hud" id="btn-ar" onclick="toggleARMode()">👓 AR Mode</button>
                    <button class="btn-hud" onclick="toggleFullscreen()">⛶ Fullscreen</button>
                </div>

                <!-- Voice / Text Command Console -->
                <div id="command-console">
                    <button id="mic-btn" title="Voice Command (Speech Recognition)" onclick="toggleVoiceRecognition()">🎙</button>
                    <input type="text" id="command-input" placeholder="Enter JARVIS command (e.g. 'show turbine', 'enable x-ray', 'focus dam', 'reset')..." onkeydown="if(event.key==='Enter') sendCommand(this.value)"/>
                    <button class="btn-hud" onclick="sendCommand(document.getElementById('command-input').value)">Execute</button>
                </div>
            </div>
        </div>

        <!-- Bundle Local Three.js and Loaders -->
        <script>
            {three_js}
        </script>
        <script>
            {controls_js}
        </script>
        <script>
            {gltf_js}
        </script>

        <script>
            const engContext = {ctx_data};
            const activeFaults = {active_faults_json};
            const currentMode = "{mode}";
            const container = document.getElementById('webgl-canvas');

            // Themes
            const themes = {{
                cyan: {{ main: '#00ffff', border: 'rgba(0, 255, 255, 0.35)', bg: 'rgba(11, 17, 32, 0.88)' }},
                gold: {{ main: '#ffbb00', border: 'rgba(255, 187, 0, 0.35)', bg: 'rgba(25, 20, 10, 0.88)' }},
                red: {{ main: '#ff3355', border: 'rgba(255, 51, 85, 0.35)', bg: 'rgba(25, 10, 15, 0.88)' }},
                purple: {{ main: '#b84dff', border: 'rgba(184, 77, 255, 0.35)', bg: 'rgba(20, 10, 28, 0.88)' }}
            }};

            function setHUDTheme(name) {{
                const t = themes[name] || themes.cyan;
                document.documentElement.style.setProperty('--hud-color', t.main);
                document.documentElement.style.setProperty('--hud-border', t.border);
                document.documentElement.style.setProperty('--hud-bg', t.bg);
                logEvent(`JARVIS: Interface HUD theme set to ${{name.toUpperCase()}}`);
            }}

            // -------------------------------------------------------------
            // Scene, Camera, Renderer Setup
            // -------------------------------------------------------------
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x070B14);

            const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.5, 1200);
            camera.position.set(75, 48, 65);

            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
            renderer.setSize(container.clientWidth || window.innerWidth, container.clientHeight || window.innerHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.shadowMap.enabled = true;
            renderer.localClippingEnabled = true;
            container.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.target.set(30, 0, 10);

            // Lighting
            const ambLight = new THREE.AmbientLight(0xffffff, 0.8);
            scene.add(ambLight);

            const dirLight = new THREE.DirectionalLight(0xffffff, 0.95);
            dirLight.position.set(90, 110, 60);
            scene.add(dirLight);

            const fillLight = new THREE.DirectionalLight(0x00ffff, 0.35);
            fillLight.position.set(-60, 40, -40);
            scene.add(fillLight);

            // Engineering Grid
            const gridHelper = new THREE.GridHelper(160, 32, 0x1E293B, 0x0F172A);
            gridHelper.position.set(30, -0.5, 0);
            scene.add(gridHelper);

            // Model Root Group
            let rootModel = null;
            let meshMap = {{}};
            let originalMaterials = new Map();
            let originalPositions = new Map();

            // Slicing Clipping Plane for Section Cutaway
            const clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 10);
            let isCutawayActive = false;

            // Load Base64 GLB
            const glbBase64 = "{glb_b64}";
            const binaryString = atob(glbBase64);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {{
                bytes[i] = binaryString.charCodeAt(i);
            }}

            const loader = new THREE.GLTFLoader();
            loader.parse(bytes.buffer, '', (gltf) => {{
                rootModel = gltf.scene;
                scene.add(rootModel);

                rootModel.traverse((child) => {{
                    if (child.isMesh) {{
                        meshMap[child.name] = child;
                        originalMaterials.set(child, child.material.clone());
                        originalPositions.set(child, child.position.clone());
                        child.castShadow = true;
                        child.receiveShadow = true;
                    }}
                }});

                // Apply active faults highlighting
                applyActiveFaults();
            }}, (err) => {{
                console.error("GLTF load error:", err);
            }});

            // -------------------------------------------------------------
            // Particle Streamlines (Water Velocity Flow)
            // -------------------------------------------------------------
            let particleSystem = null;
            let showFlow = true;
            const particleCount = 280;
            const particleGeo = new THREE.BufferGeometry();
            const particlePos = new Float32Array(particleCount * 3);

            for (let i = 0; i < particleCount; i++) {{
                const t = Math.random();
                if (i < 170) {{
                    particlePos[i * 3 + 0] = 12.0 + t * 44.0;
                    particlePos[i * 3 + 1] = (Math.random() - 0.5) * 1.5;
                    particlePos[i * 3 + 2] = 20.0 - t * 18.0;
                }} else {{
                    particlePos[i * 3 + 0] = -10.0 + t * 80.0;
                    particlePos[i * 3 + 1] = -18.0 + 1.8;
                    particlePos[i * 3 + 2] = 15.0;
                }}
            }}
            particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));
            const particleMat = new THREE.PointsMaterial({{
                color: 0x00ffff,
                size: 1.6,
                transparent: true,
                opacity: 0.9
            }});
            particleSystem = new THREE.Points(particleGeo, particleMat);
            scene.add(particleSystem);

            function animateFlow() {{
                if (!particleSystem || !showFlow) return;
                const pos = particleSystem.geometry.attributes.position.array;
                const speed = Math.max(0.2, (engContext.water_velocity_mps || 2.5) * 0.12);

                for (let i = 0; i < particleCount; i++) {{
                    if (i < 170) {{
                        pos[i * 3 + 0] += speed * 1.2;
                        pos[i * 3 + 2] -= speed * 0.5;
                        if (pos[i * 3 + 0] > 56.0) {{
                            pos[i * 3 + 0] = 12.0;
                            pos[i * 3 + 2] = 20.0;
                        }}
                    }} else {{
                        pos[i * 3 + 0] += speed * 0.9;
                        if (pos[i * 3 + 0] > 70.0) {{
                            pos[i * 3 + 0] = -10.0;
                        }}
                    }}
                }}
                particleSystem.geometry.attributes.position.needsUpdate = true;
            }}

            // Rotate Turbine Runner Blade
            function animateTurbineRotor() {{
                const turbMesh = meshMap["turbine_runner"] || meshMap["Turbine_01_MainShaft"];
                if (turbMesh) {{
                    const rpm = engContext.runner_speed_rpm || 1000.0;
                    turbMesh.rotation.y += (rpm / 60.0) * (2 * Math.PI) * 0.008;
                }}
            }}

            // -------------------------------------------------------------
            // Raycasting & Interactive Component Selection
            // -------------------------------------------------------------
            const raycaster = new THREE.Raycaster();
            const mouse = new THREE.Vector2();
            let selectedMesh = null;

            window.addEventListener('click', (event) => {{
                // Ignore clicks on HUD panels
                if (event.target.closest('#hud-topbar, #hud-left-panel, #hud-right-panel, #hud-bottom-deck')) return;

                const rect = renderer.domElement.getBoundingClientRect();
                mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
                mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

                raycaster.setFromCamera(mouse, camera);
                const intersects = raycaster.intersectObjects(Object.values(meshMap), true);

                if (intersects.length > 0) {{
                    const hit = intersects[0].object;
                    selectComponent(hit);
                }}
            }});

            function selectComponent(mesh) {{
                if (selectedMesh && originalMaterials.has(selectedMesh)) {{
                    selectedMesh.material = originalMaterials.get(selectedMesh);
                }}
                selectedMesh = mesh;

                // Highlight selected mesh with cyan emissive glow
                const hlMat = mesh.material.clone();
                hlMat.emissive = new THREE.Color(0x00ffff);
                hlMat.emissiveIntensity = 0.6;
                mesh.material = hlMat;

                updateInspector(mesh.name);
            }}

            function updateInspector(name) {{
                const badge = document.getElementById('insp-badge');
                const content = document.getElementById('inspector-content');
                badge.innerText = name.toUpperCase();

                let html = `<div style="font-weight: 800; color: var(--hud-color); margin-bottom: 8px;">${{name.toUpperCase()}}</div>`;

                if (name.includes("penstock")) {{
                    html += `
                        <div class="meta-row"><span class="meta-k">Conduit Type</span><span class="meta-v">High-Pressure Steel Penstock</span></div>
                        <div class="meta-row"><span class="meta-k">Diameter</span><span class="meta-v">${{engContext.penstock_d || 0.5}} m</span></div>
                        <div class="meta-row"><span class="meta-k">Flow Velocity</span><span class="meta-v">${{(engContext.water_velocity_mps || 2.5).toFixed(2)}} m/s</span></div>
                        <div class="meta-row"><span class="meta-k">Discharge</span><span class="meta-v">${{engContext.flow_lps || 1000}} L/s</span></div>
                        <div class="meta-row"><span class="meta-k">Head Loss</span><span class="meta-v">${{(engContext.head_loss_m || 1.5).toFixed(2)}} m</span></div>
                    `;
                }} else if (name.includes("turbine") || name.includes("runner") || name.includes("shaft")) {{
                    html += `
                        <div class="meta-row"><span class="meta-k">Subsystem</span><span class="meta-v">Reaction Turbine Runner</span></div>
                        <div class="meta-row"><span class="meta-k">Shaft Speed</span><span class="meta-v">${{(engContext.runner_speed_rpm || 1000).toFixed(0)}} RPM</span></div>
                        <div class="meta-row"><span class="meta-k">Power Output</span><span class="meta-v" style="color: #34D399;">${{(engContext.electrical_power_kw || 189).toFixed(1)}} kW</span></div>
                        <div class="meta-row"><span class="meta-k">Net Head</span><span class="meta-v">${{(engContext.net_head_m || 23.5).toFixed(2)}} m</span></div>
                        <div class="meta-row"><span class="meta-k">Efficiency</span><span class="meta-v">${{((engContext.water_to_wire_efficiency || 0.82) * 100).toFixed(1)}}%</span></div>
                    `;
                }} else if (name.includes("generator") || name.includes("stator")) {{
                    html += `
                        <div class="meta-row"><span class="meta-k">Machine</span><span class="meta-v">Synchronous 3-Phase AC</span></div>
                        <div class="meta-row"><span class="meta-k">Active Output</span><span class="meta-v" style="color: #34D399;">${{(engContext.electrical_power_kw || 189).toFixed(1)}} kW</span></div>
                        <div class="meta-row"><span class="meta-k">Grid Frequency</span><span class="meta-v">${{(engContext.frequency_hz || 50.0).toFixed(2)}} Hz</span></div>
                        <div class="meta-row"><span class="meta-k">Bearing Temp</span><span class="meta-v">48.2 °C (Nominal)</span></div>
                    `;
                }} else if (name.includes("bridge") || name.includes("conduit") || name.includes("saddle")) {{
                    html += `
                        <div class="meta-row"><span class="meta-k">Structure</span><span class="meta-v">Hydrothermal Crossing Span</span></div>
                        <div class="meta-row"><span class="meta-k">Fluid Inlet/Outlet</span><span class="meta-v">${{engContext.water_inlet_temp_c}}°C / ${{engContext.water_outlet_temp_c}}°C</span></div>
                        <div class="meta-row"><span class="meta-k">Ambient Air</span><span class="meta-v">${{engContext.ambient_air_temp_c}}°C</span></div>
                        <div class="meta-row"><span class="meta-k">Thermal Loss</span><span class="meta-v">${{(engContext.thermal_bridge_loss_kw || 0).toFixed(1)}} kW</span></div>
                        <div class="meta-row"><span class="meta-k">Expansion ΔL</span><span class="meta-v">${{(engContext.thermal_expansion_mm || 0).toFixed(2)}} mm</span></div>
                        <div class="meta-row"><span class="meta-k">Restrained Stress</span><span class="meta-v">${{(engContext.thermal_stress_mpa || 0).toFixed(2)}} MPa</span></div>
                    `;
                }} else {{
                    html += `
                        <div class="meta-row"><span class="meta-k">Element</span><span class="meta-v">${{name}}</span></div>
                        <div class="meta-row"><span class="meta-k">Status</span><span class="meta-v" style="color: #00ffff;">Operational</span></div>
                        <div class="meta-row"><span class="meta-k">Gross Head</span><span class="meta-v">${{engContext.gross_head_m}} m</span></div>
                    `;
                }}

                content.innerHTML = html;
            }}

            // -------------------------------------------------------------
            // Fault Highlighting & Camera Fly-To
            // -------------------------------------------------------------
            function applyActiveFaults() {{
                const fList = document.getElementById('faults-list');
                const counter = document.getElementById('fault-counter');

                if (!activeFaults || activeFaults.length === 0) {{
                    fList.innerHTML = `<div style="color: #64748B; font-size: 10px;">No critical faults detected. All systems nominal.</div>`;
                    counter.innerText = "0 ALERTS";
                    counter.style.color = "#34D399";
                    return;
                }}

                counter.innerText = `${{activeFaults.length}} ALERTS`;
                counter.style.color = "var(--hud-alert)";
                let listHtml = "";

                activeFaults.forEach((f, idx) => {{
                    const isCrit = f.severity === 'CRITICAL';
                    const targetName = f.component_id;
                    const mesh = meshMap[targetName] || findMatchingMesh(targetName);

                    listHtml += `
                        <div class="fault-item ${{isCrit ? 'critical' : 'warning'}}" onclick="focusFaultTarget('${{targetName}}')">
                            <div class="fault-title">
                                <span>${{f.sensor_id}}</span>
                                <span style="color: ${{isCrit ? 'var(--hud-alert)' : 'var(--hud-warn)'}};">${{f.severity}}</span>
                            </div>
                            <div style="color: #CBD5E1; margin: 3px 0;">${{f.message}}</div>
                            <div style="color: var(--hud-muted); font-size: 9px;">Target: <b>${{targetName}}</b> | Click to inspect</div>
                        </div>
                    `;

                    // Highlight 3D sub-mesh in pulsing red or amber
                    if (mesh) {{
                        const alertColor = isCrit ? 0xff2244 : 0xffaa00;
                        const mat = new THREE.MeshStandardMaterial({{
                            color: alertColor,
                            emissive: new THREE.Color(alertColor),
                            emissiveIntensity: 1.8,
                            roughness: 0.3
                        }});
                        mesh.material = mat;
                    }}
                }});

                fList.innerHTML = listHtml;
            }}

            function findMatchingMesh(target) {{
                const clean = target.toLowerCase().replace(/_/g, "");
                // ----------------------------------------------------------------
                // Expanded keyword → mesh-name matching table
                // Maps component_id tokens (from FaultEngine) to mesh name tokens
                // (from the procedural GLB model built by PlantGeometryBuilder).
                // ----------------------------------------------------------------
                const keywordMap = [
                    // Turbine / runner
                    {{ tokens: ["turbine", "turb", "mainshaft", "runner", "shaft"], meshTokens: ["turbine", "runner"] }},
                    // Spillway / gate / intake
                    {{ tokens: ["spillway", "gate", "intake", "hecrasgate", "sluice"], meshTokens: ["gate", "intake"] }},
                    // Dam / wall / crest
                    {{ tokens: ["dam", "wall", "crest", "iotdam", "damcrack", "joint"], meshTokens: ["dam", "wall"] }},
                    // Generator / bearing / stator
                    {{ tokens: ["bearing", "generator", "stator", "overheat", "thrust"], meshTokens: ["generator", "bearing"] }},
                    // Penstock / conduit / pipe
                    {{ tokens: ["penstock", "conduit", "pipe", "pressure"], meshTokens: ["penstock", "pipe"] }},
                    // Bridge / hydrothermal conduit
                    {{ tokens: ["bridge", "saddle", "span", "thermal"], meshTokens: ["bridge", "conduit"] }},
                ];

                // 1. Direct substring match (original logic)
                for (let k in meshMap) {{
                    if (k.toLowerCase().replace(/_/g, "").includes(clean)) return meshMap[k];
                }}

                // 2. Keyword table lookup
                for (const rule of keywordMap) {{
                    const tokenMatch = rule.tokens.some(tok => clean.includes(tok));
                    if (tokenMatch) {{
                        for (let k in meshMap) {{
                            const meshClean = k.toLowerCase().replace(/_/g, "");
                            if (rule.meshTokens.some(mt => meshClean.includes(mt))) {{
                                return meshMap[k];
                            }}
                        }}
                    }}
                }}

                return null;
            }}

            window.focusFaultTarget = function(partName) {{
                const targetMesh = meshMap[partName] || findMatchingMesh(partName);
                if (!targetMesh) return;

                // X-ray surrounding outer shell
                Object.values(meshMap).forEach((m) => {{
                    if (m !== targetMesh) {{
                        m.material = new THREE.MeshBasicMaterial({{
                            color: 0x00ffff,
                            wireframe: true,
                            transparent: true,
                            opacity: 0.15
                        }});
                    }}
                }});

                // Fly camera directly to bounding box center
                const box = new THREE.Box3().setFromObject(targetMesh);
                const center = box.getCenter(new THREE.Vector3());
                controls.target.copy(center);
                camera.position.set(center.x + 25, center.y + 15, center.z + 20);
                controls.update();

                updateInspector(targetMesh.name);
                logEvent(`JARVIS: Focused camera on faulty component '${{partName}}'`);
            }};

            // -------------------------------------------------------------
            // X-Ray, Explode, Section Cutaway Controls
            // -------------------------------------------------------------
            let isXRay = false;
            window.toggleXRay = function() {{
                isXRay = !isXRay;
                document.getElementById('btn-xray').classList.toggle('active', isXRay);

                Object.values(meshMap).forEach((mesh) => {{
                    if (isXRay) {{
                        mesh.material = new THREE.MeshBasicMaterial({{
                            color: 0x00ffff,
                            wireframe: true,
                            transparent: true,
                            opacity: 0.22
                        }});
                    }} else {{
                        if (originalMaterials.has(mesh)) {{
                            mesh.material = originalMaterials.get(mesh).clone();
                        }}
                    }}
                }});
                logEvent(`JARVIS: X-Ray structural inspection ${{isXRay ? 'ENABLED' : 'DISABLED'}}`);
            }};

            let isExploded = false;
            window.toggleExploded = function() {{
                isExploded = !isExploded;
                document.getElementById('btn-explode').classList.toggle('active', isExploded);

                Object.entries(meshMap).forEach(([name, mesh]) => {{
                    const orig = originalPositions.get(mesh) || new THREE.Vector3();
                    if (isExploded) {{
                        // Displace components outward radially
                        if (name.includes("turbine") || name.includes("runner")) {{
                            mesh.position.set(orig.x, orig.y, orig.z - 10);
                        }} else if (name.includes("generator")) {{
                            mesh.position.set(orig.x, orig.y, orig.z + 14);
                        }} else if (name.includes("powerhouse")) {{
                            mesh.position.set(orig.x + 18, orig.y, orig.z);
                        }} else if (name.includes("gate")) {{
                            mesh.position.set(orig.x, orig.y, orig.z + 12);
                        }} else if (name.includes("bridge") || name.includes("conduit")) {{
                            mesh.position.set(orig.x, orig.y - 15, orig.z);
                        }}
                    }} else {{
                        mesh.position.copy(orig);
                    }}
                }});
                logEvent(`JARVIS: Assembly exploded view ${{isExploded ? 'EXPANDED' : 'COLLAPSED'}}`);
            }};

            window.toggleCutaway = function() {{
                isCutawayActive = !isCutawayActive;
                document.getElementById('btn-cutaway').classList.toggle('active', isCutawayActive);

                if (isCutawayActive) {{
                    renderer.clippingPlanes = [clipPlane];
                }} else {{
                    renderer.clippingPlanes = [];
                }}
                logEvent(`JARVIS: Dynamic Section Plane ${{isCutawayActive ? 'ACTIVE' : 'INACTIVE'}}`);
            }};

            window.toggleFlowStreamlines = function() {{
                showFlow = !showFlow;
                document.getElementById('btn-flow').classList.toggle('active', showFlow);
                if (particleSystem) particleSystem.visible = showFlow;
            }};

            window.resetCamera = function() {{
                camera.position.set(75, 48, 65);
                controls.target.set(30, 0, 10);
                controls.update();
                // Restore materials
                Object.values(meshMap).forEach((m) => {{
                    if (originalMaterials.has(m)) m.material = originalMaterials.get(m).clone();
                }});
                isXRay = false;
                isExploded = false;
                document.getElementById('btn-xray').classList.remove('active');
                document.getElementById('btn-explode').classList.remove('active');
                logEvent("JARVIS: 3D Camera and viewport reset.");
            }};

            window.toggleFullscreen = function() {{
                const el = document.getElementById('jarvis-container');
                if (!document.fullscreenElement) el.requestFullscreen();
                else document.exitFullscreen();
            }};

            // -------------------------------------------------------------
            // Camera Passthrough Augmented Reality (WebAR)
            // -------------------------------------------------------------
            let isARMode = false;
            let arStream = null;

            window.toggleARMode = function() {{
                const btn = document.getElementById('btn-ar');
                const video = document.getElementById('ar-camera-feed');
                const notif = document.getElementById('ar-notification');

                if (!isARMode) {{
                    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {{
                        navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: "environment" }} }})
                            .then((stream) => {{
                                arStream = stream;
                                video.srcObject = stream;
                                video.style.display = "block";
                                scene.background = null;  // Transparent WebGL background over video
                                isARMode = true;
                                btn.classList.add('active');
                                showNotification("👓 AR Camera Passthrough Active: 3D model anchored in physical space.");
                                logEvent("JARVIS: Augmented Reality camera passthrough enabled.");
                            }})
                            .catch((err) => {{
                                showNotification("⚠️ Camera access unavailable: " + err.message + ". Preserving desktop 3D.");
                                logEvent("JARVIS: AR activation failed - hardware camera unavailable.");
                            }});
                    }} else {{
                        showNotification("⚠️ WebAR camera API not supported by current browser environment.");
                    }}
                }} else {{
                    if (arStream) {{
                        arStream.getTracks().forEach(track => track.stop());
                        arStream = null;
                    }}
                    video.style.display = "none";
                    scene.background = new THREE.Color(0x070B14);
                    isARMode = false;
                    btn.classList.remove('active');
                    showNotification("AR Mode deactivated. Returned to standard 3D viewport.");
                    logEvent("JARVIS: AR camera passthrough closed.");
                }}
            }};

            function showNotification(msg) {{
                const el = document.getElementById('ar-notification');
                el.innerText = msg;
                el.style.display = "block";
                setTimeout(() => {{ el.style.display = "none"; }}, 4500);
            }}

            // -------------------------------------------------------------
            // Local Voice & Natural Text Command Registry
            // -------------------------------------------------------------
            window.sendCommand = function(cmd) {{
                if (!cmd || !cmd.trim()) return;
                const clean = cmd.trim().toLowerCase();
                document.getElementById('command-input').value = "";

                logEvent(`User: "${{cmd}}"`);

                if (clean.includes("turbine") || clean.includes("runner")) {{
                    focusFaultTarget("turbine_runner");
                }} else if (clean.includes("dam") || clean.includes("wall")) {{
                    focusFaultTarget("dam_structure");
                }} else if (clean.includes("bridge") || clean.includes("conduit")) {{
                    focusFaultTarget("bridge_deck");
                }} else if (clean.includes("penstock") || clean.includes("pipe")) {{
                    focusFaultTarget("penstock_pipe");
                }} else if (clean.includes("gate")) {{
                    focusFaultTarget("intake_gate");
                }} else if (clean.includes("x-ray") || clean.includes("xray")) {{
                    toggleXRay();
                }} else if (clean.includes("explode") || clean.includes("explosion")) {{
                    toggleExploded();
                }} else if (clean.includes("cutaway") || clean.includes("section")) {{
                    toggleCutaway();
                }} else if (clean.includes("flow") || clean.includes("water")) {{
                    toggleFlowStreamlines();
                }} else if (clean.includes("ar") || clean.includes("reality") || clean.includes("camera")) {{
                    toggleARMode();
                }} else if (clean.includes("reset") || clean.includes("restore")) {{
                    resetCamera();
                }} else if (clean.includes("cyan")) {{
                    setHUDTheme('cyan');
                }} else if (clean.includes("gold") || clean.includes("amber")) {{
                    setHUDTheme('gold');
                }} else if (clean.includes("red")) {{
                    setHUDTheme('red');
                }} else if (clean.includes("purple")) {{
                    setHUDTheme('purple');
                }} else if (clean.includes("fault") || clean.includes("alert")) {{
                    if (activeFaults.length > 0) {{
                        focusFaultTarget(activeFaults[0].component_id);
                    }} else {{
                        showNotification("JARVIS: All system parameters nominal. No active faults.");
                    }}
                }} else {{
                    showNotification(`JARVIS: Command not recognized: '${{cmd}}'. Try 'show turbine', 'enable x-ray', or 'reset'.`);
                }}
            }};

            // Web Speech API Integration
            let speechRec = null;
            let isListening = false;

            window.toggleVoiceRecognition = function() {{
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                const micBtn = document.getElementById('mic-btn');

                if (!SpeechRecognition) {{
                    showNotification("Speech recognition API not supported by browser. Use text command box.");
                    return;
                }}

                if (!isListening) {{
                    speechRec = new SpeechRecognition();
                    speechRec.continuous = false;
                    speechRec.interimResults = false;
                    speechRec.lang = 'en-US';

                    speechRec.onstart = () => {{
                        isListening = true;
                        micBtn.classList.add('listening');
                        showNotification("🎙 JARVIS listening... Speak command (e.g. 'show turbine', 'enable x-ray')");
                    }};

                    speechRec.onresult = (e) => {{
                        const transcript = e.results[0][0].transcript;
                        sendCommand(transcript);
                    }};

                    speechRec.onerror = (e) => {{
                        console.warn("Speech error:", e);
                        isListening = false;
                        micBtn.classList.remove('listening');
                    }};

                    speechRec.onend = () => {{
                        isListening = false;
                        micBtn.classList.remove('listening');
                    }};

                    speechRec.start();
                }} else {{
                    if (speechRec) speechRec.stop();
                    isListening = false;
                    micBtn.classList.remove('listening');
                }}
            }};

            function logEvent(msg) {{
                console.log(`[JARVIS HUD] ${{msg}}`);
            }}

            window.addEventListener('resize', () => {{
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});

            // Master Animation Loop
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                animateFlow();
                animateTurbineRotor();
                renderer.render(scene, camera);
            }}
            animate();
        </script>
    </body>
    </html>
    """

    st.components.v1.html(html_code, height=height, scrolling=False)
