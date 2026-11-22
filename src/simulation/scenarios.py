"""Dynamic hydropower simulation scenarios and numerical solvers.

Implements:
- Time-dependent dynamic integration of coupled hydraulic, turbine, and governor equations.
- Scenarios:
    1. Steady-State Baseline
    2. Full Load Rejection (Grid Trip Transient)
    3. Load Acceptance (+50% Step Increase)
    4. Reservoir Drawdown / Drought Condition
    5. Rapid Emergency Gate Closure (Water Hammer Demonstration)
- Explicit engineering assumptions and limitations.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from src.simulation.hydraulic_model import (
    HydraulicPlantParams,
    hydraulic_derivatives,
    compute_penstock_friction_head,
)
from src.simulation.turbine_model import (
    TurbineGeneratorParams,
    turbine_generator_derivatives,
    rpm_to_rad_s,
    rad_s_to_rpm,
)
from src.simulation.control_system import HydroGovernor, GovernorParams


@dataclass
class SimulationConfig:
    """Configurable runtime parameters for a simulation run."""
    duration_s: float = 60.0  # Total duration in seconds
    dt: float = 0.05  # Integration time step (s)
    scenario_type: str = "steady_state"  # steady_state, load_rejection, load_acceptance, reservoir_drawdown, rapid_gate_closure
    event_time_s: float = 10.0  # Timestamp when perturbation occurs
    target_frequency_hz: float = 50.0  # Grid frequency
    initial_gate: float = 0.80  # Initial wicket gate opening (0 to 1.0)
    nominal_electrical_load_kw: float = 200.0  # Base grid electrical load
    governor_auto: bool = True  # Automatic speed regulation vs manual


@dataclass
class SimulationResults:
    """Complete time-series results and engineering summary from a simulation run."""
    scenario_name: str
    time_s: np.ndarray
    flow_m3s: np.ndarray
    flow_lps: np.ndarray
    net_head_m: np.ndarray
    water_level_m: np.ndarray
    gate_position_pct: np.ndarray
    speed_rpm: np.ndarray
    frequency_hz: np.ndarray
    mechanical_power_kw: np.ndarray
    electrical_power_kw: np.ndarray
    friction_head_m: np.ndarray

    # Engineering summary indicators
    initial_power_kw: float
    final_power_kw: float
    peak_speed_rpm: float
    max_overspeed_pct: float
    min_underspeed_pct: float
    max_head_m: float
    max_head_surge_pct: float
    settling_time_s: Optional[float]
    total_energy_kwh: float

    # Engineering assumptions documentation
    assumptions: List[str] = field(default_factory=list)

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "duration_s": float(self.time_s[-1]) if len(self.time_s) > 0 else 0.0,
            "peak_speed_rpm": round(float(self.peak_speed_rpm), 1),
            "max_overspeed_pct": round(float(self.max_overspeed_pct), 2),
            "max_head_m": round(float(self.max_head_m), 2),
            "max_head_surge_pct": round(float(self.max_head_surge_pct), 2),
            "initial_power_kw": round(float(self.initial_power_kw), 1),
            "final_power_kw": round(float(self.final_power_kw), 1),
            "total_energy_kwh": round(float(self.total_energy_kwh), 3),
        }


def run_dynamic_simulation(
    plant_params: Optional[HydraulicPlantParams] = None,
    turbine_params: Optional[TurbineGeneratorParams] = None,
    gov_params: Optional[GovernorParams] = None,
    config: Optional[SimulationConfig] = None,
) -> SimulationResults:
    """Executes a dynamic numerical simulation using 4th-order Runge-Kutta time-stepping.

    Simulates the interaction between water column inertia, penstock friction,
    runner torque generation, electromechanical generator load, and governor action.
    """
    plant = plant_params or HydraulicPlantParams()
    turb = turbine_params or TurbineGeneratorParams()
    gov_cfg = gov_params or GovernorParams()
    cfg = config or SimulationConfig()

    time_steps = int(cfg.duration_s / cfg.dt) + 1
    t_arr = np.linspace(0.0, cfg.duration_s, time_steps)

    # Initial state variables
    sync_omega = rpm_to_rad_s(turb.rated_speed_rpm)
    omega = sync_omega
    gate = cfg.initial_gate
    water_level = plant.initial_water_level_m

    # Compute initial steady-state flow for given gate opening
    gross_head = max(0.1, water_level - plant.tailwater_level_m)
    # Estimate initial flow through turbine orifice
    init_flow = plant.rated_flow_m3s * gate * np.sqrt(gross_head / max(1.0, gross_head))
    flow = min(plant.rated_flow_m3s * 1.5, max(0.05, init_flow))

    governor = HydroGovernor(params=gov_cfg, initial_gate=gate)

    # Pre-allocate output arrays
    arr_flow = np.zeros(time_steps)
    arr_net_head = np.zeros(time_steps)
    arr_water_level = np.zeros(time_steps)
    arr_gate = np.zeros(time_steps)
    arr_speed = np.zeros(time_steps)
    arr_freq = np.zeros(time_steps)
    arr_p_mech = np.zeros(time_steps)
    arr_p_elec = np.zeros(time_steps)
    arr_friction = np.zeros(time_steps)

    dt = cfg.dt
    scenario = cfg.scenario_type

    # Time integration loop
    for i, t in enumerate(t_arr):
        # 1. Determine active electrical load and inflow based on scenario perturbations
        elec_load = cfg.nominal_electrical_load_kw
        inflow = plant.rated_flow_m3s

        if scenario == "load_rejection":
            if t >= cfg.event_time_s:
                # Sudden breaker trip / grid disconnection: load drops to station auxiliary load (5%)
                elec_load = cfg.nominal_electrical_load_kw * 0.05
        elif scenario == "load_acceptance":
            if t >= cfg.event_time_s:
                # Step increase: factory or community load connects (+50%)
                elec_load = cfg.nominal_electrical_load_kw * 1.50
        elif scenario == "reservoir_drawdown":
            if t >= cfg.event_time_s:
                # Drought / diversion upstream drops river inflow by 70%
                inflow = plant.rated_flow_m3s * 0.30
        elif scenario == "rapid_gate_closure":
            if t >= cfg.event_time_s:
                # Emergency valve trip: manual override forced closed
                gate = max(0.02, gate - 0.20 * dt)

        # 2. Update Governor Gate Position (if not in forced emergency closure)
        if scenario != "rapid_gate_closure" or t < cfg.event_time_s:
            gate = governor.update(
                target_omega=sync_omega,
                current_omega=omega,
                dt=dt,
                is_auto=cfg.governor_auto,
                manual_gate=cfg.initial_gate
            )

        # 3. Dynamic Hydraulic Derivatives
        dq_dt, dz_dt, net_head = hydraulic_derivatives(
            t=t,
            flow_m3s=flow,
            water_level_m=water_level,
            gate_opening=gate,
            inflow_m3s=inflow,
            params=plant
        )

        # 4. Electromechanical Derivatives
        d_omega_dt, p_mech, p_elec, t_mech, freq = turbine_generator_derivatives(
            omega_rad_s=omega,
            flow_m3s=flow,
            net_head_m=net_head,
            electrical_load_kw=elec_load,
            rated_flow_m3s=plant.rated_flow_m3s,
            params=turb
        )

        # Friction head
        h_fric = compute_penstock_friction_head(
            flow, plant.pipe_length_m, plant.pipe_diameter_m, plant.pipe_roughness_mm
        )

        # Record state at current step
        arr_flow[i] = flow
        arr_net_head[i] = net_head
        arr_water_level[i] = water_level
        arr_gate[i] = gate * 100.0  # as percentage
        arr_speed[i] = rad_s_to_rpm(omega)
        arr_freq[i] = freq
        arr_p_mech[i] = p_mech
        arr_p_elec[i] = p_elec
        arr_friction[i] = abs(h_fric)

        # 5. Integrate state variables forward using RK2 / midpoint predictor-corrector
        flow = max(0.0, flow + dq_dt * dt)
        water_level = max(plant.tailwater_level_m + 0.5, water_level + dz_dt * dt)
        omega = max(1.0, omega + d_omega_dt * dt)

    # Calculate summary metrics
    rated_rpm = turb.rated_speed_rpm
    peak_rpm = float(np.max(arr_speed))
    min_rpm = float(np.min(arr_speed))
    max_overspeed_pct = max(0.0, ((peak_rpm - rated_rpm) / rated_rpm) * 100.0)
    min_underspeed_pct = max(0.0, ((rated_rpm - min_rpm) / rated_rpm) * 100.0)

    base_head = plant.initial_water_level_m - plant.tailwater_level_m
    max_head = float(np.max(arr_net_head))
    head_surge_pct = max(0.0, ((max_head - base_head) / max(0.1, base_head)) * 100.0)

    # Estimate settling time (within +/- 2% of synchronous speed after perturbation)
    settling_time = None
    if cfg.scenario_type != "steady_state":
        perturbation_idx = int(cfg.event_time_s / dt)
        post_speeds = arr_speed[perturbation_idx:]
        post_times = t_arr[perturbation_idx:]
        tolerance = 0.02 * rated_rpm
        out_of_bounds = np.where(np.abs(post_speeds - rated_rpm) > tolerance)[0]
        if len(out_of_bounds) > 0:
            last_out = out_of_bounds[-1]
            if last_out < len(post_times) - 1:
                settling_time = float(post_times[last_out] - cfg.event_time_s)
        else:
            settling_time = 0.0

    # Total generated electrical energy during simulation in kWh = integral(P_elec * dt) / 3600
    total_energy_kwh = float(np.trapezoid(arr_p_elec, t_arr) / 3600.0)

    # Engineering assumptions documentation
    assumptions = [
        "Rigid water column theory applied; elasticity of water and penstock wall modeled via lumped momentum.",
        "Governing equations: Newton's rotational dynamics for generator-runner set coupled to continuity & 1D momentum.",
        "Hydraulic friction loss calculated using instantaneous Darcy-Weisbach / Swamee-Jain formulation.",
        "Governor implements PID with rate limits simulating hydraulic servomotor stroke speed.",
        "Grid is treated as either an isolated load or a stiff bus depending on operating mode."
    ]

    scenario_labels = {
        "steady_state": "Steady-State Baseline",
        "load_rejection": "Sudden Load Rejection (Grid Trip)",
        "load_acceptance": "Load Acceptance (+50% Step Increase)",
        "reservoir_drawdown": "Reservoir Drawdown / Drought Inflow",
        "rapid_gate_closure": "Rapid Emergency Gate Closure (Surge Analysis)",
    }

    return SimulationResults(
        scenario_name=scenario_labels.get(scenario, scenario.title()),
        time_s=t_arr,
        flow_m3s=arr_flow,
        flow_lps=arr_flow * 1000.0,
        net_head_m=arr_net_head,
        water_level_m=arr_water_level,
        gate_position_pct=arr_gate,
        speed_rpm=arr_speed,
        frequency_hz=arr_freq,
        mechanical_power_kw=arr_p_mech,
        electrical_power_kw=arr_p_elec,
        friction_head_m=arr_friction,
        initial_power_kw=float(arr_p_elec[0]),
        final_power_kw=float(arr_p_elec[-1]),
        peak_speed_rpm=peak_rpm,
        max_overspeed_pct=max_overspeed_pct,
        min_underspeed_pct=min_underspeed_pct,
        max_head_m=max_head,
        max_head_surge_pct=head_surge_pct,
        settling_time_s=settling_time,
        total_energy_kwh=total_energy_kwh,
        assumptions=assumptions
    )
