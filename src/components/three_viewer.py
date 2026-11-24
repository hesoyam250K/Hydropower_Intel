"""Interactive Three.js 3D Engineering and Holographic Viewer component.

Locally bundles Three.js, OrbitControls, and GLTFLoader for 100% offline operation.
Supports:
1. Interactive 3D Viewer with mouse orbit, pan, zoom, component selection raycasting,
   HUD engineering inspection panels, and Flow/Thermal/Structural visual modes.
2. Pepper's Ghost 4-View Synchronized Hologram Display.
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
from src.components.jarvis_viewer import render_jarvis_viewer


STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "three"


def load_local_js(filename: str) -> str:
    """Reads locally bundled JavaScript file."""
    path = STATIC_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def render_threejs_viewer(
    context: SharedEngineeringContext,
    builder: Optional[PlantGeometryBuilder] = None,
    mode: str = "FLOW",
    model_filter: str = "BOTH",  # 'BOTH', 'HYDROPOWER_ONLY', 'BRIDGE_ONLY'
    height: int = 650
) -> None:
    """Renders the interactive Three.js 3D engineering viewer inside Streamlit."""
    include_bridge = model_filter in ("BOTH", "BRIDGE_ONLY")
    actual_builder = builder or PlantGeometryBuilder(
        gross_head_m=context.gross_head_m,
        pipe_diameter_m=context.penstock_d if hasattr(context, "penstock_d") else 0.50,
        bridge_length_m=60.0,
        include_bridge=include_bridge
    )

    # Generate GLB in memory
    glb_bytes = build_scene_and_export_glb(builder=actual_builder, context=context, mode=mode)
    glb_b64 = base64.b64encode(glb_bytes).decode("utf-8")

    three_js = load_local_js("three.min.js")
    controls_js = load_local_js("OrbitControls.js")
    gltf_js = load_local_js("GLTFLoader.js")

    ctx_data = json.dumps(context.to_dict())

    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body, html {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background-color: #0B1120;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }}
            #canvas-container {{
                width: 100%;
                height: 100%;
                position: relative;
            }}
            #ui-overlay {{
                position: absolute;
                top: 12px;
                left: 12px;
                z-index: 10;
                background: rgba(15, 23, 42, 0.88);
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px 14px;
                color: #F8FAFC;
                font-size: 11px;
                backdrop-filter: blur(4px);
                max-width: 320px;
                pointer-events: auto;
            }}
            #controls-bar {{
                position: absolute;
                bottom: 12px;
                left: 12px;
                z-index: 10;
                display: flex;
                gap: 8px;
            }}
            button.btn-ctrl {{
                background: #1E293B;
                border: 1px solid #475569;
                color: #F8FAFC;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }}
            button.btn-ctrl:hover {{
                background: #2563EB;
                border-color: #38BDF8;
            }}
            #legend-bar {{
                position: absolute;
                bottom: 12px;
                right: 12px;
                z-index: 10;
                background: rgba(15, 23, 42, 0.88);
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F8FAFC;
                font-size: 10px;
            }}
            .ramp {{
                width: 140px;
                height: 10px;
                border-radius: 3px;
                margin-top: 4px;
            }}
            .ramp-flow {{
                background: linear-gradient(to right, #38BDF8, #0284C7, #EF4444);
            }}
            .ramp-thermal {{
                background: linear-gradient(to right, #1E40AF, #06B6D4, #10B981, #FBBF24, #EF4444);
            }}
            .ramp-stress {{
                background: linear-gradient(to right, #10B981, #F59E0B, #DC2626);
            }}
            #hud-inspector {{
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid #334155;
                font-size: 10.5px;
            }}
        </style>
    </head>
    <body>
        <div id="canvas-container">
            <div id="ui-overlay">
                <div style="font-weight: 700; color: #38BDF8; margin-bottom: 4px;">
                    HYDROPOWER & HYDROTHERMAL 3D VIEWER
                </div>
                <div style="color: #94A3B8;">Mode: <b style="color: #F8FAFC;">{mode}</b> | Model: <b style="color: #F8FAFC;">{model_filter}</b></div>
                <div id="hud-inspector">
                    <span style="color: #64748B;">Click any 3D component to inspect engineering metadata.</span>
                </div>
            </div>

            <div id="controls-bar">
                <button class="btn-ctrl" onclick="resetCamera()">Reset Camera</button>
                <button class="btn-ctrl" onclick="toggleWireframe()">Wireframe</button>
                <button class="btn-ctrl" onclick="toggleParticles()">Toggle Flow</button>
                <button class="btn-ctrl" onclick="toggleFullscreen()">Fullscreen</button>
            </div>

            <div id="legend-bar">
                <div id="legend-title" style="font-weight: bold; margin-bottom: 2px;">Velocity Scale (m/s)</div>
                <div id="legend-ramp" class="ramp ramp-flow"></div>
                <div id="legend-labels" style="display: flex; justify-content: space-between; margin-top: 2px; color: #94A3B8;">
                    <span>0.5 m/s</span>
                    <span>2.5 m/s</span>
                    <span>>4.0 m/s</span>
                </div>
            </div>
        </div>

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
            const currentMode = "{mode}";
            const container = document.getElementById('canvas-container');

            // Setup Scene, Camera, Renderer
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0B1120);

            const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.5, 1000);
            camera.position.set(70, 45, 60);

            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.shadowMap.enabled = true;
            container.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.target.set(30, 0, 10);

            // Lighting
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
            scene.add(ambientLight);

            const dirLight = new THREE.DirectionalLight(0xffffff, 0.9);
            dirLight.position.set(80, 100, 50);
            scene.add(dirLight);

            const fillLight = new THREE.DirectionalLight(0x38BDF8, 0.4);
            fillLight.position.set(-60, 40, -40);
            scene.add(fillLight);

            // Grid & Axes Helper
            const gridHelper = new THREE.GridHelper(140, 28, 0x334155, 0x1E293B);
            gridHelper.position.set(30, 0, 0);
            gridHelper.rotation.x = Math.PI / 2;
            scene.add(gridHelper);

            let rootModel = null;
            let interactiveMeshes = [];
            let isWireframe = false;

            // Load Embedded Base64 GLB
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
                        interactiveMeshes.push(child);
                        child.castShadow = true;
                        child.receiveShadow = true;
                        child.material.side = THREE.DoubleSide;
                    }}
                }});
            }}, (err) => {{
                console.error("GLTF load error:", err);
            }});

            // -------------------------------------------------------------
            // Animated Flow Particles System (Simulated Water Streamlines)
            // -------------------------------------------------------------
            let particleSystem = null;
            let showParticles = true;
            const particleCount = 250;
            const particleGeometry = new THREE.BufferGeometry();
            const particlePositions = new Float32Array(particleCount * 3);

            // Seed particles along penstock and conduit path
            for (let i = 0; i < particleCount; i++) {{
                const t = Math.random();
                if (i < 150) {{
                    // Penstock trajectory from intake to powerhouse
                    particlePositions[i * 3 + 0] = 12.0 + t * 44.0;
                    particlePositions[i * 3 + 1] = (Math.random() - 0.5) * 1.5;
                    particlePositions[i * 3 + 2] = 20.0 - t * 18.0;
                }} else {{
                    // Hydrothermal bridge conduit path
                    particlePositions[i * 3 + 0] = -10.0 + t * 80.0;
                    particlePositions[i * 3 + 1] = -18.0 + 1.8;
                    particlePositions[i * 3 + 2] = 15.0;
                }}
            }}
            particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));

            const particleMaterial = new THREE.PointsMaterial({{
                color: 0x38BDF8,
                size: 1.4,
                transparent: true,
                opacity: 0.85
            }});
            particleSystem = new THREE.Points(particleGeometry, particleMaterial);
            scene.add(particleSystem);

            // Animate Particles along streamlines
            function animateParticles() {{
                if (!particleSystem || !showParticles) return;
                const pos = particleSystem.geometry.attributes.position.array;
                const speed = Math.max(0.2, (engContext.water_velocity_mps || 2.5) * 0.1);

                for (let i = 0; i < particleCount; i++) {{
                    if (i < 150) {{
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

            // -------------------------------------------------------------
            // Raycasting & Interactive Component Inspection
            // -------------------------------------------------------------
            const raycaster = new THREE.Raycaster();
            const mouse = new THREE.Vector2();
            let selectedObject = null;
            let originalMaterial = null;

            container.addEventListener('click', (event) => {{
                const rect = renderer.domElement.getBoundingClientRect();
                mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
                mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

                raycaster.setFromCamera(mouse, camera);
                const intersects = raycaster.intersectObjects(interactiveMeshes, true);

                if (intersects.length > 0) {{
                    const hit = intersects[0].object;
                    highlightObject(hit);
                }}
            }});

            function highlightObject(obj) {{
                if (selectedObject && originalMaterial) {{
                    selectedObject.material = originalMaterial;
                }}
                selectedObject = obj;
                originalMaterial = obj.material.clone();

                // Create highlight material
                const hlMat = obj.material.clone();
                hlMat.emissive = new THREE.Color(0x38BDF8);
                hlMat.emissiveIntensity = 0.45;
                obj.material = hlMat;

                updateHUD(obj.name);
            }}

            function updateHUD(name) {{
                const hud = document.getElementById('hud-inspector');
                let infoHtml = `<div style="font-weight: bold; color: #F8FAFC; margin-bottom: 3px;">${{name.toUpperCase()}}</div>`;

                if (name.includes("penstock")) {{
                    infoHtml += `
                        <div>Diameter: <b>${{engContext.penstock_d || 0.5}} m</b></div>
                        <div>Flow Velocity: <b>${{(engContext.water_velocity_mps || 2.5).toFixed(2)}} m/s</b></div>
                        <div>Discharge Q: <b>${{engContext.flow_lps || 1000}} L/s</b></div>
                        <div>Head Loss: <b>${{(engContext.head_loss_m || 1.5).toFixed(2)}} m</b></div>
                    `;
                }} else if (name.includes("turbine") || name.includes("generator") || name.includes("powerhouse")) {{
                    infoHtml += `
                        <div>Power Output: <b style="color: #34D399;">${{(engContext.electrical_power_kw || 189).toFixed(1)}} kW</b></div>
                        <div>Effective Net Head: <b>${{(engContext.net_head_m || 23.5).toFixed(2)}} m</b></div>
                        <div>Runner Speed: <b>${{engContext.runner_speed_rpm || 1000}} RPM</b></div>
                        <div>Frequency: <b>${{(engContext.frequency_hz || 50.0).toFixed(2)}} Hz</b></div>
                        <div>Efficiency: <b>${{((engContext.water_to_wire_efficiency || 0.82) * 100).toFixed(1)}}%</b></div>
                    `;
                }} else if (name.includes("bridge") || name.includes("conduit") || name.includes("pier") || name.includes("saddle")) {{
                    infoHtml += `
                        <div>Inlet / Outlet Temp: <b>${{engContext.water_inlet_temp_c}}°C / ${{engContext.water_outlet_temp_c}}°C</b></div>
                        <div>Ambient Air Temp: <b>${{engContext.ambient_air_temp_c}}°C</b></div>
                        <div>Fluid Heat Transfer: <b>${{(engContext.fluid_thermal_transfer_kw || 0).toFixed(1)}} kW</b></div>
                        <div>Conductive Bridge Loss: <b>${{(engContext.thermal_bridge_loss_kw || 0).toFixed(1)}} kW</b></div>
                        <div>Thermal Expansion: <b>${{(engContext.thermal_expansion_mm || 0).toFixed(2)}} mm</b></div>
                        <div>Restrained Stress: <b>${{(engContext.thermal_stress_mpa || 0).toFixed(2)}} MPa</b></div>
                    `;
                }} else {{
                    infoHtml += `
                        <div>Subsystem: <b>${{engContext.project_name}}</b></div>
                        <div>Status: <b style="color: #38BDF8;">Operational</b></div>
                        <div>Gross Head: <b>${{engContext.gross_head_m}} m</b></div>
                    `;
                }}
                hud.innerHTML = infoHtml;
            }}

            // Configure Legend UI
            const lTitle = document.getElementById('legend-title');
            const lRamp = document.getElementById('legend-ramp');
            const lLabels = document.getElementById('legend-labels');

            if (currentMode === "THERMAL") {{
                lTitle.innerText = "Temperature Field (°C)";
                lRamp.className = "ramp ramp-thermal";
                lLabels.innerHTML = `<span>${{engContext.ambient_air_temp_c}}°C</span><span>${{((engContext.water_inlet_temp_c + engContext.ambient_air_temp_c)/2).toFixed(1)}}°C</span><span>${{engContext.water_inlet_temp_c}}°C</span>`;
            }} else if (currentMode === "STRUCTURAL") {{
                lTitle.innerText = "Thermal Stress σ (MPa)";
                lRamp.className = "ramp ramp-stress";
                lLabels.innerHTML = `<span>0 MPa</span><span>15 MPa</span><span>>30 MPa</span>`;
            }}

            // Controls
            window.resetCamera = function() {{
                camera.position.set(70, 45, 60);
                controls.target.set(30, 0, 10);
                controls.update();
            }};

            window.toggleWireframe = function() {{
                isWireframe = !isWireframe;
                interactiveMeshes.forEach(mesh => {{
                    mesh.material.wireframe = isWireframe;
                }});
            }};

            window.toggleParticles = function() {{
                showParticles = !showParticles;
                if (particleSystem) particleSystem.visible = showParticles;
            }};

            window.toggleFullscreen = function() {{
                if (!document.fullscreenElement) {{
                    container.requestFullscreen();
                }} else {{
                    document.exitFullscreen();
                }}
            }};

            window.addEventListener('resize', () => {{
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            }});

            // Animation Loop
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                animateParticles();
                renderer.render(scene, camera);
            }}
            animate();
        </script>
    </body>
    </html>
    """

    st.components.v1.html(html_code, height=height, scrolling=False)


def render_peppers_ghost_hologram(
    context: SharedEngineeringContext,
    builder: Optional[PlantGeometryBuilder] = None,
    mode: str = "FLOW",
    height: int = 750
) -> None:
    """Renders a synchronized 4-view Pepper's Ghost optical pyramid hologram layout."""
    actual_builder = builder or PlantGeometryBuilder(
        gross_head_m=context.gross_head_m,
        include_bridge=True
    )
    glb_bytes = build_scene_and_export_glb(builder=actual_builder, context=context, mode=mode)
    glb_b64 = base64.b64encode(glb_bytes).decode("utf-8")

    three_js = load_local_js("three.min.js")
    gltf_js = load_local_js("GLTFLoader.js")

    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body, html {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background-color: #000000;
                color: #FFFFFF;
                font-family: monospace;
            }}
            #hologram-stage {{
                width: 100vw;
                height: 100vh;
                position: relative;
                background: #000000;
            }}
            #pyramid-apex-marker {{
                position: absolute;
                top: 50%;
                left: 50%;
                width: 16px;
                height: 16px;
                transform: translate(-50%, -50%);
                border: 1px dashed rgba(255, 255, 255, 0.4);
                border-radius: 50%;
                pointer-events: none;
                z-index: 5;
            }}
            #holo-ctrl {{
                position: absolute;
                top: 8px;
                left: 8px;
                z-index: 20;
                background: rgba(20, 20, 20, 0.9);
                padding: 8px 12px;
                border-radius: 4px;
                border: 1px solid #333;
                font-size: 11px;
            }}
            button.holo-btn {{
                background: #222;
                color: #00FFCC;
                border: 1px solid #00FFCC;
                padding: 4px 8px;
                font-size: 10px;
                cursor: pointer;
                margin-right: 4px;
            }}
            button.holo-btn:hover {{
                background: #00FFCC;
                color: #000;
            }}
        </style>
    </head>
    <body>
        <div id="holo-ctrl">
            <span style="color: #00FFCC; font-weight: bold;">PEPPER'S GHOST 4-VIEW PYRAMID</span> |
            <button class="holo-btn" onclick="toggleRotation()">Toggle Rotation</button>
            <button class="holo-btn" onclick="adjustScale(1.15)">Scale +</button>
            <button class="holo-btn" onclick="adjustScale(0.85)">Scale -</button>
            <button class="holo-btn" onclick="toggleFullscreen()">Fullscreen</button>
        </div>

        <div id="hologram-stage">
            <div id="pyramid-apex-marker"></div>
        </div>

        <script>
            {three_js}
        </script>
        <script>
            {gltf_js}
        </script>

        <script>
            const container = document.getElementById('hologram-stage');
            const W = window.innerWidth;
            const H = window.innerHeight;

            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
            renderer.setSize(W, H);
            renderer.setClearColor(0x000000, 1.0);
            container.appendChild(renderer.domElement);

            // Create Master Scene
            const scene = new THREE.Scene();

            const ambientLight = new THREE.AmbientLight(0xFFFFFF, 0.9);
            scene.add(ambientLight);

            const keyLight = new THREE.DirectionalLight(0x38BDF8, 1.2);
            keyLight.position.set(50, 80, 50);
            scene.add(keyLight);

            // Camera setup: 4 Orthogonal cameras for Front, Back, Left, Right
            const views = [
                // Top View (Facing North)
                {{ left: 0.35, bottom: 0.60, width: 0.30, height: 0.35, rotZ: 0, camPos: [30, 70, 10] }},
                // Bottom View (Facing South, Inverted 180°)
                {{ left: 0.35, bottom: 0.05, width: 0.30, height: 0.35, rotZ: Math.PI, camPos: [30, -70, 10] }},
                // Left View (Facing West, 90°)
                {{ left: 0.05, bottom: 0.33, width: 0.30, height: 0.35, rotZ: -Math.PI/2, camPos: [-40, 0, 10] }},
                // Right View (Facing East, -90°)
                {{ left: 0.65, bottom: 0.33, width: 0.30, height: 0.35, rotZ: Math.PI/2, camPos: [100, 0, 10] }}
            ];

            let modelGroup = new THREE.Group();
            scene.add(modelGroup);

            // Load Base64 GLB
            const glbBase64 = "{glb_b64}";
            const binaryString = atob(glbBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {{
                bytes[i] = binaryString.charCodeAt(i);
            }}

            const loader = new THREE.GLTFLoader();
            loader.parse(bytes.buffer, '', (gltf) => {{
                const loaded = gltf.scene;
                loaded.position.set(-30, 0, -10); // Center pivot
                modelGroup.add(loaded);
            }});

            let isRotating = true;
            let currentScale = 1.0;

            window.toggleRotation = function() {{ isRotating = !isRotating; }};
            window.adjustScale = function(factor) {{
                currentScale *= factor;
                modelGroup.scale.set(currentScale, currentScale, currentScale);
            }};
            window.toggleFullscreen = function() {{
                if (!document.fullscreenElement) container.requestFullscreen();
                else document.exitFullscreen();
            }};

            // Render 4 Quad-Viewports synchronized
            function render() {{
                requestAnimationFrame(render);

                if (isRotating) {{
                    modelGroup.rotation.z += 0.012;
                }}

                renderer.setScissorTest(true);

                views.forEach((v) => {{
                    const x = Math.floor(W * v.left);
                    const y = Math.floor(H * v.bottom);
                    const w = Math.floor(W * v.width);
                    const h = Math.floor(H * v.height);

                    renderer.setViewport(x, y, w, h);
                    renderer.setScissor(x, y, w, h);

                    const cam = new THREE.PerspectiveCamera(40, w / h, 1, 500);
                    cam.position.set(v.camPos[0], v.camPos[1], v.camPos[2]);
                    cam.lookAt(0, 0, 0);
                    cam.rotation.z = v.rotZ;

                    renderer.render(scene, cam);
                }});

                renderer.setScissorTest(false);
            }}
            render();

            window.addEventListener('resize', () => {{
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});
        </script>
    </body>
    </html>
    """

    st.components.v1.html(html_code, height=height, scrolling=False)
