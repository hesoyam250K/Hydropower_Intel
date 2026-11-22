# HydroPower Intelligence
### Desktop-First Hydropower Engineering & Dynamic Simulation Suite

**HydroPower Intelligence** is an integrated desktop engineering application designed for civil engineering students, mechanical and electrical power engineers, and plant operators. It combines three core engineering workflows in a single desktop application:

1. **Hydraulic Sizing & Power Calculator**: Rigorous hydraulic friction and minor loss modeling (Darcy-Weisbach & Hazen-Williams), water-to-wire power output, and turbine regime classification.
2. **Physics & Governor Dynamic Simulation Lab**: 1D lumped-parameter dynamic modeling of water column inertia, penstock momentum, reservoir continuity, turbine rotational mechanics, and electro-hydraulic PID governor transient response (Runge-Kutta ODE solver).
3. **Live SCADA Telemetry & Sensor Monitoring**: Dual-mode operating architecture supporting reproducible synthetic telemetry streams and integration-ready local MQTT ingestion for ESP32 microcontrollers and industrial PLCs.

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
Standard coefficients include bellmouth intake ($K=0.05$), standard 90° elbow ($K=0.35$), gate valve fully open ($K=0.15$), and submerged tailrace exit ($K=1.0$).

#### Hazen-Williams Empirical Formulation (Metric)
$$h_f = 10.67 \times \frac{L \times Q^{1.852}}{C^{1.852} \times D^{4.870}}$$
*Applicability & Limits*: Strictly valid for turbulent flow of water at standard ambient temperatures (~15°C–25°C) in circular conduits ($D \ge 0.05 \text{ m}$). Unlike Darcy-Weisbach, Hazen-Williams ignores kinematic viscosity and temperature effects.

### 1.3 Turbomachinery Classification & Specific Speed
Turbine selection is evaluated based on effective net head, design discharge, and specific speed:

- **Metric Specific Speed ($N_s$)**:
  $$N_s = \frac{N \sqrt{P_{kW}}}{H_{net}^{1.25}}$$
- **Kinematic Specific Speed ($n_q$)**:
  $$n_q = \frac{N \sqrt{Q_{m3s}}}{H_{net}^{0.75}}$$
- **High Head ($H_{net} > 50\text{ m}$)**: Pelton impulse turbine (or Turgo). Characterized by high partial-load efficiency and atmospheric casing.
- **Medium Head ($15\text{ m} \le H_{net} \le 400\text{ m}$)**: Francis mixed-flow reaction turbine. High peak efficiency (90–94%), sensitive to part-load cavitation.
- **Low Head / High Flow ($H_{net} < 30\text{ m}$)**: Kaplan double-regulated axial turbine or propeller turbine.

### 1.4 Dynamic Simulation Equations
The Simulation Lab couples three differential equations:
1. **Penstock Fluid Momentum (Water Column Inertia)**:
   $$\frac{dQ}{dt} = \frac{g A}{L} \left( H_{res}(t) - H_{tail} - h_{friction}(Q) - H_{turb}(Q, a) \right)$$
2. **Reservoir Mass Balance**:
   $$\frac{dZ_{res}}{dt} = \frac{Q_{inflow}(t) - Q(t)}{A_{res}}$$
3. **Runner-Generator Rotational Dynamics (Newton's 2nd Law)**:
   $$J \frac{d\omega}{dt} = T_m(Q, H, \omega) - T_e(\omega, P_{load}) - D (\omega - \omega_0)$$
4. **Hydro Governor**: PID servomotor controlling gate opening fraction $a(t) \in [0.05, 1.00]$ with stroke rate limiting ($|da/dt| \le \text{rate\_limit}$).

---

## 2. Technology Stack

- **Language**: Python 3.10+ (tested on Python 3.15).
- **Interface**: Streamlit (custom industrial dark charcoal styling).
- **Calculations & Solvers**: NumPy & SciPy (ODE integration, implicit root finding).
- **Engineering Plots**: Matplotlib.
- **Data Structures**: Pandas.
- **Storage**: Local embedded SQLite database (zero cloud dependency).
- **Telemetry**: `paho-mqtt` for local broker communication; internal synthetic stochastic generator.
- **Reporting**: ReportLab for on-the-fly offline engineering PDF generation.
- **Testing**: Pytest (32 automated unit and verification tests).

---

## 3. Project Architecture

```
HydroPower-Intelligence/
├── .streamlit/
│   └── config.toml               # Industrial dark theme configuration
├── data/
│   └── hydropower_intelligence.db # Embedded persistent SQLite database
├── src/
│   ├── app.py                    # Main Streamlit application and navigation router
│   ├── engine/
│   │   ├── hydropower.py         # Fundamental hydropower equations and substitutions
│   │   ├── head_loss.py          # Darcy-Weisbach, Hazen-Williams, and minor losses
│   │   ├── turbine.py            # Specific speed, selection rules, and part-load curves
│   │   └── validation.py         # Physical bounds checking and warning thresholds
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
│   └── components/
│       ├── styles.py             # Custom industrial CSS and branding banners
│       ├── dashboard.py          # Overview / Executive Dashboard
│       ├── project_manager.py    # Scheme creation, parameters, and persistence
│       ├── calculator.py         # Power Calculator workspace
│       ├── simulator.py          # Simulation Lab workspace
│       ├── monitoring.py         # Live Telemetry & SCADA monitoring
│       ├── analytics_view.py     # Sensitivity sweeps and comparisons
│       ├── insights_view.py      # Rule-based engineering observations
│       ├── reports_view.py       # Formal PDF generator and data exports
│       └── settings_view.py      # Constants, units, and SQLite diagnostics
├── tests/
│   ├── test_hydropower.py        # Core equations & reference verification
│   ├── test_head_loss.py         # Darcy, Colebrook, and Hazen-Williams tests
│   ├── test_turbine.py           # Specific speed & efficiency curve tests
│   ├── test_validation.py        # Physical limits and boundary tests
│   ├── test_simulation.py        # Transient ODE and governor stability tests
│   ├── test_storage.py           # SQLite persistence and CRUD tests
│   ├── test_telemetry.py         # Threshold alarms and sensor decoding tests
│   └── test_analytics_and_reports.py # PDF generation & parametric sweeps tests
├── launcher.py                   # Python desktop launch script
├── run.bat                       # One-click Windows desktop batch launcher
├── requirements.txt              # Pinned Python package dependencies
└── README.md                     # Documentation and engineering manual
```

---

## 4. Installation & Desktop Launch

### 4.1 Prerequisites
- Windows 10/11 (or Linux/macOS)
- Python 3.10, 3.11, 3.12, 3.13, 3.14, or 3.15 installed and added to your `PATH`.

### 4.2 Installation
In the project directory, install the required libraries:
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

The application will open immediately in your default browser at `http://localhost:8501`.

---

## 5. Automated Verification & Testing

Run the automated Pytest test suite:
```bash
pytest tests/
```

### Reference Calculation Benchmark Test
The calculation engine is continuously verified against the standard engineering benchmark:
- **Discharge ($Q$)**: $1,000 \text{ L/s} = 1.0 \text{ m}^3/\text{s}$
- **Gross Head ($H_{gross}$)**: $20.0 \text{ m}$
- **Head Loss ($H_{loss}$)**: $2.0 \text{ m}$
- **Efficiency ($\eta$)**: $0.75$
- **Operating Time**: $24.0 \text{ hours}$

**Expected Outputs**:
- Effective Net Head: $H_{net} = 20 - 2 = 18.0 \text{ m}$
- Instantaneous Electrical Power:
  $$P = \frac{1000 \times 9.81 \times 1.0 \times 18.0 \times 0.75}{1000} = 132.435 \text{ kW}$$
- Daily Electrical Energy:
  $$E = 132.435 \text{ kW} \times 24 \text{ h} = 3,178.44 \text{ kWh}$$

*Test status*: Passing (`tests/test_hydropower.py::test_reference_hydropower_calculation`).

---

## 6. Physical Sensor Hardware Integration (ESP32 / PLC)

The application provides an asynchronous, non-blocking MQTT telemetry client ready for field deployment.

### Field Deployment Wiring / Protocol
1. Run a local MQTT broker on your plant network (e.g., Eclipse Mosquitto on `localhost:1883` or a Raspberry Pi gateway).
2. Configure your ESP32 or PLC to publish JSON sensor packets at 1 Hz to the topic:
   `hydropower/telemetry/station1`
3. Standard payload format:
   ```json
   {
     "timestamp": "2026-11-22T12:00:00",
     "flow_lps": 1150.4,
     "net_head_m": 29.8,
     "power_kw": 224.5,
     "frequency_hz": 50.02,
     "voltage_v": 401.5,
     "current_a": 365.2,
     "gate_pct": 82.0,
     "bearing_temp_c": 44.2,
     "vibration_mms": 1.45
   }
   ```
4. In **Live Telemetry**, select *Physical Sensor Integration (MQTT)*, enter your broker IP, and click **Connect to Local MQTT Broker**.

---

## 7. Engineering Assumptions & Limitations

1. **Fluid Density & Gravity**: Assumes standard freshwater density ($\rho = 1,000 \text{ kg/m}^3$) and standard sea-level gravity ($g = 9.81 \text{ m/s}^2$). For high-altitude sites (e.g. >2,000m) or high sediment-laden rivers (e.g. glacial flour), density should be adjusted in System Configuration.
2. **Hydraulic Friction Model**: Steady-state 1D pipe flow equations are applied. Multi-phase flow, air entrainment at the intake, and sediment transport deposition require site-specific sediment trap and desanding basin designs.
3. **Dynamic Simulation**: The Simulation Lab implements rigid lumped water column theory with instantaneous Darcy friction and second-order rotational dynamics. High-frequency 2D acoustic water hammer pressure waves and elastic pipe-wall dilation (Allievi method of characteristics) are simplified into lumped inertial momentum.
4. **Civil Engineering Scope**: This software is designed as a sizing, investigation, and engineering education tool. It does not replace site geotechnical boring logs, seismic dam stability analysis, flood spillway routing, or environmental fish-passage design.

---

## 8. License & Authorship

Developed as a desktop-first engineering software application adhering to classical hydraulic principles and civil engineering design standards.
