# HydroPower Intelligence
### Desktop-First Hydropower Engineering, Hydrothermal Bridge Analysis & 3D Holographic Visualization Suite

**HydroPower Intelligence** is an integrated desktop engineering application designed for civil engineering students, mechanical and electrical power engineers, and plant operators. It combines four core engineering workflows in a single desktop application:

1. **Hydraulic Sizing & Power Calculator**: Rigorous pipe friction and minor loss modeling (Darcy-Weisbach with Colebrook-White, Swamee-Jain, and Churchill formulations, or Hazen-Williams), water-to-wire power output, and turbine regime classification.
2. **Physics & Governor Dynamic Simulation Lab**: 1D lumped-parameter dynamic modeling of water column inertia, penstock momentum, reservoir continuity, turbine rotational mechanics, and electro-hydraulic PID governor transient response (Runge-Kutta ODE solver).
3. **Live SCADA Telemetry & Sensor Monitoring**: Dual-mode operating architecture supporting reproducible synthetic stochastic telemetry streams and integration-ready local MQTT ingestion for ESP32 microcontrollers and industrial PLCs.
4. **Hydrothermal Bridge Analysis & 3D Hologram Lab (v1.1)**: Coupled convective-conductive thermal transfer, structural thermal expansion, restrained thermal stress, GPU-accelerated Three.js 3D WebGL digital twin, and synchronized 4-view Pepper's Ghost optical hologram projection.

---

## 1. Core Engineering Mathematics & Governing Principles

### 1.1 The Fundamental Hydropower Equation
Hydroelectric generation converts the potential and kinetic energy of water into shaft torque and electric power:

$$P = \rho \times g \times Q \times H_{net} \times \eta$$

- **$P$ (Electric Power Output)**: Watts (W). Divided by 1,000 for kilowatts (kW).
- **$\rho$ (Water Density)**: $\approx 1,000 \text{ kg/m}^3$ (standard freshwater approximation).
- **$g$ (Gravitational Acceleration)**: $9.81 \text{ m/s}^2$.
- **$Q$ (Volumetric Flow Rate)**: Measured in cubic metres per second ($\text{m}^3/\text{s}$). Conversion from Litres per second ($\text{L/s}$):
  $$Q(\text{m}^3/\text{s}) = \frac{Q(\text{L/s})}{1,000}$$
- **$H_{net}$ (Effective Net Head)**: Elevation drop minus all hydraulic pipe friction and fitting minor losses:
  $$H_{net} = \max\left(0, H_{gross} - H_{loss}\right)$$
- **$\eta$ (Water-to-Wire Combined Efficiency)**: Product of runner hydraulic efficiency, generator electromechanical efficiency, and transformer coupling ($\eta = \eta_t \times \eta_g \times \eta_{trans}$, typically 0.75 to 0.90).
- **$E$ (Electrical Energy Production)**:
  $$E(\text{kWh}) = P(\text{kW}) \times \text{Operating Hours}$$
  $$E_{annual}(\text{MWh}) = \frac{P(\text{kW}) \times 8,760 \text{ h} \times C_f}{1,000}$$

### 1.2 Hydraulic Head Loss Calculations

#### Darcy-Weisbach Formulation (Theoretical & Rigorous)
$$h_f = f \times \frac{L}{D} \times \frac{v^2}{2g}$$

Where mean flow velocity is derived from continuity:
$$v = \frac{4 Q}{\pi D^2}$$

The friction factor $f$ is solved dynamically across all Reynolds regimes ($Re = v D / \nu$):
- **Laminar ($Re \le 2000$)**: Hagen-Poiseuille equation:
  $$f = \frac{64}{Re}$$
- **Transition ($2000 < Re < 4000$)**: Churchill continuous cubic formulation.
- **Turbulent ($Re \ge 4000$)**: Implicit Colebrook-White equation solved numerically via Brent's method with Swamee-Jain explicit seed:
  $$\frac{1}{\sqrt{f}} = -2 \log_{10}\left(\frac{\epsilon / D}{3.7} + \frac{2.51}{Re \sqrt{f}}\right)$$

#### Minor Losses (Fittings, Valves, Transitions)
$$h_m = \sum K \times \frac{v^2}{2g}$$

#### Hazen-Williams Empirical Formulation (Metric)
$$h_f = 10.67 \times \frac{L \times Q^{1.852}}{C^{1.852} \times D^{4.870}}$$

### 1.3 Turbomachinery Classification & Specific Speed
- **Metric Specific Speed ($N_s$)**: $N_s = \frac{N \sqrt{P_{kW}}}{H_{net}^{1.25}}$
- **Kinematic Specific Speed ($n_q$)**: $n_q = \frac{N \sqrt{Q_{m3s}}}{H_{net}^{0.75}}$
- **High Head ($H_{net} > 50\text{ m}$)**: Pelton impulse turbine.
- **Medium Head ($15\text{ m} \le H_{net} \le 400\text{ m}$)**: Francis reaction turbine.
- **Low Head / High Flow ($H_{net} < 30\text{ m}$)**: Kaplan axial turbine.

### 1.4 Coupled Hydrothermal Bridge & Conduit Analysis (v1.1)

#### Convective Fluid Thermal Transport
$$Q_{thermal} = \dot{m} \times c_p \times (T_{in} - T_{out})$$
Where:
- $\dot{m} = \rho \times Q$ is fluid mass flow rate ($\text{kg/s}$).
- $c_p \approx 4,184 \text{ J/kg}\cdot\text{K}$ is freshwater specific heat capacity.
- $T_{in}, T_{out}$ are inlet and outlet fluid temperatures (°C).
- Sign preservation: $Q_{thermal} > 0$ denotes heat lost to the environment (cooling); $Q_{thermal} < 0$ denotes heat absorbed (warming).

#### Conductive Thermal Bridge Loss (U-Value Method)
$$Q_{cond} = U \times A \times (T_{fluid,avg} - T_{ambient})$$
Where $U$ is overall heat-transfer coefficient ($\text{W/m}^2\cdot\text{K}$), $A$ is exposed heat-transfer area ($\text{m}^2$), and $T_{fluid,avg} = 0.5(T_{in} + T_{out})$.

#### 1D Fourier's Conduction Law
$$q = -k \nabla T \approx k \times \frac{T_{inner} - T_{outer}}{t_{wall}}$$

#### Linear Thermal Expansion
$$\Delta L = \alpha \times L_0 \times \Delta T$$
Where $\alpha$ is material thermal expansion coefficient ($1/\text{K}$), $L_0$ is initial span length (m), and $\Delta T = T_{structure} - T_{datum}$.

#### Restrained Thermal Stress
$$\sigma_{th} = R \times E \times \alpha \times \Delta T$$
Where $R \in [0.0, 1.0]$ is the structural restraint coefficient ($R = 1.0$ fully fixed, $R = 0.5$ semi-restrained, $R = 0.0$ free sliding expansion joint), and $E$ is Young's modulus (MPa).
*Civil Engineering Qualification*: This represents an idealized 1D unaxial estimate; it provides preliminary screening and does not replace multi-axial finite element analysis (FEA).

---

## 2. Technology Stack

- **Language**: Python 3.10+ (tested on Python 3.15).
- **Interface**: Streamlit (custom industrial dark charcoal styling).
- **Calculations & Solvers**: NumPy & SciPy (ODE integration, implicit root finding).
- **3D Geometry & Meshing**: Trimesh & PyVista.
- **3D Rendering & Holograms**: Three.js (r128, bundled locally with OrbitControls and GLTFLoader).
- **Engineering Plots**: Matplotlib.
- **Data Structures**: Pandas.
- **Storage**: Local embedded SQLite database (zero cloud dependency).
- **Telemetry**: `paho-mqtt` for local broker communication; internal synthetic stochastic generator.
- **Reporting**: ReportLab for on-the-fly offline engineering PDF generation.
- **Testing**: Pytest (48 automated unit and verification tests).

---

## 3. Project Architecture

```
HydroPower-Intelligence/
├── .streamlit/
│   └── config.toml               # Industrial dark theme configuration
├── data/
│   ├── hydropower_intelligence.db # Embedded persistent SQLite database
│   └── models/
│       └── hydropower_bridge_model.glb # Bundled 3D plant & bridge digital twin
├── src/
│   ├── app.py                    # Main Streamlit application and navigation router
│   ├── engine/
│   │   ├── hydropower.py         # Fundamental hydropower equations and substitutions
│   │   ├── head_loss.py          # Darcy-Weisbach, Hazen-Williams, and minor losses
│   │   ├── turbine.py            # Specific speed, selection rules, and part-load curves
│   │   ├── validation.py         # Physical bounds checking and warning thresholds
│   │   └── shared_data.py        # Central SharedEngineeringContext cross-module bridge
│   ├── hydrothermal/             # Coupled hydrothermal & thermal-structural engine
│   │   ├── materials.py          # Material database (concrete, steel, aluminum, etc.)
│   │   ├── boundary_conditions.py# Thermal and structural boundary conditions
│   │   ├── heat_transfer.py      # Convective, conductive, and Fourier calculations
│   │   ├── structural.py         # Thermal expansion, stress, and restraint analysis
│   │   ├── thermal_bridge.py     # Composite wall R-values and condensation risk
│   │   └── validation.py         # Hydrothermal physical limits validation
│   ├── geometry/                 # 3D procedural modeling & mesh pipeline
│   │   ├── mesh_builder.py       # PlantGeometryBuilder for hydropower + bridge solids
│   │   └── exporter.py           # GLB binary exporter with field colormapping
│   ├── simulation/
│   │   ├── hydraulic_model.py    # Fluid momentum and continuity ODEs
│   │   ├── turbine_model.py      # Electromechanical rotational dynamics
│   │   ├── control_system.py     # PID speed governor and servomotor rate limits
│   │   └── scenarios.py          # Transient simulation runner (RK time-stepping)
│   ├── telemetry/
│   │   ├── sensor_manager.py     # Telemetry data structures and alarm thresholds
│   │   ├── simulated_data.py     # Stochastic synthetic sensor stream generator
│   │   └── mqtt_client.py        # Asynchronous paho-mqtt client for ESP32/PLC
│   ├── analytics/
│   │   ├── performance.py        # Parametric sweeps (diameter, flow, tariff matrix)
│   │   └── reports.py            # Local PDF report generator & CSV exporters
│   ├── database/
│   │   └── storage.py            # SQLite schema, migrations, and CRUD operations
│   ├── insights/
│   │   └── interpretation.py     # Offline rule-based diagnostic interpretation engine
│   ├── static/three/             # Bundled local Three.js offline scripts
│   │   ├── three.min.js          # Three.js r128 core engine
│   │   ├── OrbitControls.js      # Orbit camera controls
│   │   └── GLTFLoader.js         # GLTF/GLB binary parser
│   └── components/               # Modular Streamlit UI workspaces
│       ├── styles.py             # Custom industrial CSS and branding banners
│       ├── dashboard.py          # Section A: Overview Dashboard
│       ├── project_manager.py    # Section B: Project Manager
│       ├── calculator.py         # Section C: Power Calculator Workspace
│       ├── simulator.py          # Section D: Dynamic Simulation Lab
│       ├── monitoring.py         # Section E: Live Telemetry & SCADA
│       ├── hydrothermal_lab_view.py # Section F: Hydrothermal & 3D Lab
│       ├── three_viewer.py       # Three.js 3D viewer & Pepper's Ghost renderer
│       ├── analytics_view.py     # Section G: Analytics & Sensitivity
│       ├── insights_view.py      # Section H: Engineering Insights
│       ├── reports_view.py       # Section I: Reports & Exports
│       └── settings_view.py      # Section J: System Configuration
├── tests/                        # 48 Automated Pytest verification tests
│   ├── test_hydropower.py        # Benchmark calculation verification
│   ├── test_head_loss.py         # Friction loss formulations
│   ├── test_turbine.py           # Specific speed & efficiency curve tests
│   ├── test_validation.py        # Boundary tests
│   ├── test_simulation.py        # Transient ODE and governor stability tests
│   ├── test_storage.py           # SQLite persistence and CRUD tests
│   ├── test_telemetry.py         # Threshold alarms and sensor decoding tests
│   ├── test_analytics_and_reports.py # PDF report & CSV export tests
│   ├── test_hydrothermal.py      # Hydrothermal heat & structural stress tests
│   ├── test_shared_data.py       # Cross-module shared context integration tests
│   └── test_geometry_and_mesh.py # 3D mesh building & GLB export tests
├── launcher.py                   # Python desktop launch script
├── run.bat                       # One-click Windows desktop batch launcher
├── requirements.txt              # Pinned Python package dependencies
└── README.md                     # Documentation and engineering manual
```

---

## 4. Installation & Desktop Launch

### 4.1 Prerequisites
- Windows 10/11 (or Linux/macOS)
- Python 3.10+ installed and added to `PATH`.

### 4.2 Installation
```bash
pip install -r requirements.txt
```

### 4.3 Launching the Application
- **Option 1 (Windows Desktop Launcher)**:
  Double-click `run.bat` in File Explorer.
- **Option 2 (Python Launcher)**:
  ```bash
  python launcher.py
  ```
- **Option 3 (Direct Streamlit CLI)**:
  ```bash
  streamlit run src/app.py
  ```

Access the interface at `http://localhost:8501`. Operates 100% offline without remote APIs or CDNs.

---

## 5. Using the Hydrothermal & 3D Lab

Navigate to **Hydrothermal & 3D Lab** in the sidebar:

### A. Hydrothermal Analysis
1. Configure conduit length, heat transfer area, wall thickness, and structural material (concrete, steel, aluminum, HDPE, insulation).
2. Set fluid temperatures ($T_{in}, T_{out}$), ambient air temperature, and boundary restraint ($R = 1.0$ fixed, $R = 0.5$ semi-restrained, $R = 0.0$ free).
3. Review fluid mass flow, convective heat transfer, conductive bridge loss, linear thermal expansion, and restrained thermal stress.

### B. 3D Engineering Viewer
- **Mouse Controls**: Left Click + Drag to rotate | Right Click + Drag to pan | Mouse Wheel to zoom.
- **Component Raycasting**: Click on any component (penstock, turbine, generator, bridge deck, pier) to inspect its live engineering metadata in the HUD panel.
- **Overlays**: Switch between Flow Mode (particle streamlines color-coded by velocity), Thermal Mode (temperature field in °C), and Structural Mode (stress in MPa).
- **Subsystem Filter**: View Both, Hydropower Installation Only, or Hydrothermal Bridge Only.
- **Playback & SCADA**: Replay recorded Simulation Lab transients with the timeline scrubber or stream live SCADA sensor readings directly into the 3D scene.
- **Export**: Download GLB 3D model files with embedded vertex fields directly to your desktop.

### C. Hologram Display (Pepper's Ghost 4-View Pyramid)
- Renders 4 synchronized orthogonal viewports (North, South-inverted, East, West) on a pitch-black background.
- Position a 4-sided DIY transparent acrylic/glass pyramid inverted over the center crosshair.
- The 4 views reflect off the angled transparent walls to form a floating 3D optical hologram in mid-air.
- Includes rotation toggle, scale adjustment, and fullscreen mode.

---

## 6. Automated Verification & Testing

Run all 48 automated tests:
```bash
pytest
```

Output:
```
============================= 48 passed in 36.23s =============================
```

### Verification Benchmark
- **Hydraulic Reference**: $Q = 1000\text{ L/s}$, $H_{gross} = 20\text{ m}$, $H_{loss} = 2\text{ m}$, $\eta = 0.75 \implies H_{net} = 18.0\text{ m}, P = 132.435\text{ kW}, E = 3178.44\text{ kWh}$.
- **Hydrothermal Reference**: Convective transfer $Q = \dot{m} c_p \Delta T$, Fourier 1D conduction $q = -k \nabla T$, thermal expansion $\Delta L = \alpha L_0 \Delta T$, and restrained stress $\sigma = R E \alpha \Delta T$.

---

## 7. Engineering Assumptions & Limitations

1. **Fluid Density & Heat Capacity**: Freshwater standard values ($\rho = 1,000 \text{ kg/m}^3$, $c_p = 4,184 \text{ J/kg}\cdot\text{K}$).
2. **Thermal Analysis Scope**: Solves 1D energy balance and U-value conductive heat loss. Conjugate heat transfer (CHT) with full Navier-Stokes energy coupling (OpenFOAM / FEniCS) is supported structurally in the pipeline architecture, but not executed directly as a mandatory dependency.
3. **Structural Thermal Stress**: Employs Saint-Venant unaxial beam restraint theory ($\sigma = R \cdot E \cdot \alpha \cdot \Delta T$). 3D multi-axial thermal gradient distributions require site-specific structural FEA.
4. **Offline Operation**: All Three.js scripts, 3D meshes, and database files reside locally on the host machine.
