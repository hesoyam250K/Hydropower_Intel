"""Rule-based engineering interpretation and diagnostics engine.

Examines hydraulic calculations and dynamic simulation outputs to deliver
structured, educational engineering observations grounded in fluid mechanics
and civil/electromechanical hydropower engineering principles.
Operates completely offline without external AI APIs.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.engine.hydropower import HydropowerCalculationResult
from src.simulation.scenarios import SimulationResults


@dataclass
class EngineeringObservation:
    """An individual engineering insight or diagnostic observation."""
    category: str  # 'Hydraulics', 'Turbine Selection', 'Economics & Energy', 'Transient Dynamics'
    level: str  # 'INFO', 'OPTIMIZATION', 'WARNING', 'CRITICAL'
    title: str
    observation: str
    recommendation: str
    governing_principle: str


def generate_calculation_insights(calc: HydropowerCalculationResult) -> List[EngineeringObservation]:
    """Generates structured engineering observations from a hydropower calculation."""
    insights: List[EngineeringObservation] = []

    # 1. Head Loss Ratio Analysis
    gross_head = calc.gross_head_m
    head_loss = calc.head_loss_m
    loss_ratio = (head_loss / gross_head * 100.0) if gross_head > 0 else 0.0

    if loss_ratio > 15.0:
        # High friction loss
        current_d = calc.loss_breakdown.pipe_diameter_m if calc.loss_breakdown else 0.5
        next_d = current_d * 1.2
        recovered_power = calc.hydraulic_power_kw * (head_loss * 0.5 / max(1.0, calc.net_head_m))
        insights.append(EngineeringObservation(
            category="Hydraulics",
            level="WARNING",
            title="Excessive Penstock Friction Losses (>15% of Gross Head)",
            observation=(
                f"Hydraulic head loss is {head_loss:.2f} m, representing {loss_ratio:.1f}% of gross head. "
                "This dissipates substantial potential energy as turbulent friction heat along the pipe walls."
            ),
            recommendation=(
                f"Evaluate increasing the internal penstock diameter from {current_d*1000:.0f} mm to {next_d*1000:.0f} mm. "
                f"Because head loss varies inversely with diameter to the ~4.87 power (hf ∝ D⁻⁴·⁸⁷), "
                f"a 20% diameter increase will reduce friction loss by ~60%, recovering an estimated {recovered_power:.1f} kW."
            ),
            governing_principle="Darcy-Weisbach / Hazen-Williams diameter sensitivity (hf ∝ L·Q² / D⁵)"
        ))
    elif loss_ratio > 8.0:
        insights.append(EngineeringObservation(
            category="Hydraulics",
            level="OPTIMIZATION",
            title="Moderate Penstock Head Loss (8% - 15%)",
            observation=(
                f"Penstock head loss represents {loss_ratio:.1f}% of gross head. This falls near the upper edge "
                "of standard economic design guidelines (typically 5% to 10%)."
            ),
            recommendation=(
                "Perform a life-cycle cost analysis comparing the capital cost of a larger pipe diameter "
                "against the net present value (NPV) of additional electricity generation over a 30-year design life."
            ),
            governing_principle="Economic Penstock Sizing (Trade-off between Pipe Capital Cost vs Lifetime Energy Loss)"
        ))
    elif loss_ratio < 2.0 and head_loss > 0:
        insights.append(EngineeringObservation(
            category="Hydraulics",
            level="INFO",
            title="Generously Sized Penstock (Head Loss < 2%)",
            observation=(
                f"Hydraulic head loss is minimal ({loss_ratio:.1f}% of gross head). The water conveyance system operates "
                "with exceptional hydraulic efficiency."
            ),
            recommendation=(
                "Verify whether penstock material and installation costs were over-budgeted. A slightly smaller diameter "
                "might substantially reduce capital expenditure without meaningful generation loss."
            ),
            governing_principle="Civil Infrastructure Cost Optimization"
        ))

    # 2. Flow Velocity Assessment (if pipe dimensions available)
    if calc.loss_breakdown:
        v = calc.loss_breakdown.flow_velocity_mps
        if v > 4.0:
            insights.append(EngineeringObservation(
                category="Hydraulics",
                level="WARNING",
                title=f"High Flow Velocity ({v:.2f} m/s)",
                observation=(
                    f"Mean flow velocity of {v:.2f} m/s exceeds recommended penstock design limits (1.5 - 3.5 m/s). "
                    "High velocities induce rapid dynamic pressure surges during valve movements and accelerate wall abrasion."
                ),
                recommendation=(
                    "Increase pipe diameter to bring velocity below 3.0 m/s. "
                    "If velocity cannot be reduced, specify abrasion-resistant internal linings and slow-closing valve actuators."
                ),
                governing_principle="Continuity equation (v = 4Q / πD²) and Joukowsky surge pressure (ΔH = a·Δv / g)"
            ))
        elif v < 1.0 and v > 0.05:
            insights.append(EngineeringObservation(
                category="Hydraulics",
                level="OPTIMIZATION",
                title=f"Low Flow Velocity ({v:.2f} m/s)",
                observation=(
                    f"Mean flow velocity of {v:.2f} m/s is below typical self-cleansing velocity (~1.2 - 1.5 m/s). "
                    "Sediment, silt, and sand carried in river water may settle along lower penstock sections."
                ),
                recommendation=(
                    "Ensure adequate sand/gravel traps (desanders) at the intake works, "
                    "or reduce pipe diameter to maintain scouring velocity."
                ),
                governing_principle="Sediment Transport Mechanics & Hjulström self-cleansing velocity criteria"
            ))

    # 3. Turbine Regime & Specific Speed Insight
    if calc.turbine_selection:
        ts = calc.turbine_selection
        insights.append(EngineeringObservation(
            category="Turbine Selection",
            level="INFO",
            title=f"Recommended Turbine: {ts.primary_recommendation}",
            observation=(
                f"Operating regime: {ts.regime_category} with net head of {calc.net_head_m:.1f} m and "
                f"flow of {calc.flow_m3s:.3f} m³/s. "
                + (f"Specific speed Ns ≈ {ts.metric_specific_speed_ns:.0f} rpm·kW^0.5·m^-1.25." if ts.metric_specific_speed_ns else "")
            ),
            recommendation=(
                f"Primary choice is {ts.primary_recommendation}. Alternative options: {', '.join(ts.secondary_options) if ts.secondary_options else 'None'}. "
                f"Cavitation risk assessment: {ts.cavitation_risk}."
            ),
            governing_principle="Specific Speed Ns Classification & Dimensionless Turbomachinery Scaling Laws"
        ))

    # 4. Energy Generation & Plant Capacity
    if calc.annual_energy_mwh > 0:
        annual_val_estimate = calc.annual_energy_mwh * 1000.0 * 0.10  # assume $0.10 / kWh benchmark
        insights.append(EngineeringObservation(
            category="Economics & Energy",
            level="INFO",
            title=f"Annual Generation Potential: {calc.annual_energy_mwh:,.1f} MWh/year",
            observation=(
                f"Continuous generation at {calc.capacity_factor*100:.0f}% capacity factor yields "
                f"{calc.annual_energy_mwh:,.1f} MWh annually (equivalent to ~{calc.annual_energy_mwh / 3.5:.0f} average residential households)."
            ),
            recommendation=(
                f"At a representative electricity export tariff of $0.10/kWh, expected gross annual revenue is ~${annual_val_estimate:,.0f}. "
                "Integrate seasonal Flow Duration Curve (FDC) data to refine wet vs dry season generation forecasts."
            ),
            governing_principle="Energy Integral E = ∫ P·dt and Flow Duration Curve (FDC) Integration"
        ))

    return insights


def generate_simulation_insights(sim: SimulationResults) -> List[EngineeringObservation]:
    """Generates structured engineering observations from dynamic simulation results."""
    insights: List[EngineeringObservation] = []

    # 1. Overspeed transient analysis
    if sim.max_overspeed_pct > 35.0:
        insights.append(EngineeringObservation(
            category="Transient Dynamics",
            level="CRITICAL",
            title=f"Excessive Runner Overspeed ({sim.max_overspeed_pct:.1f}%)",
            observation=(
                f"During the transient event, rotational speed surged to {sim.peak_speed_rpm:.0f} RPM "
                f"({sim.max_overspeed_pct:.1f}% above rated synchronous speed). "
                "Severe overspeed imposes extreme centrifugal stresses on runner blades and generator rotor poles."
            ),
            recommendation=(
                "Increase rotating assembly moment of inertia (J) by specifying a generator flywheel, "
                "or tighten governor proportional and derivative gains for faster gate intervention."
            ),
            governing_principle="Newton's Rotational Dynamics (J · dω/dt = Tm - Te) and Mechanical Centrifugal Stress"
        ))
    elif sim.max_overspeed_pct > 15.0:
        insights.append(EngineeringObservation(
            category="Transient Dynamics",
            level="WARNING",
            title=f"Moderate Speed Rise ({sim.max_overspeed_pct:.1f}%)",
            observation=(
                f"Peak speed rose to {sim.peak_speed_rpm:.0f} RPM during load rejection. "
                "Governor successfully contained runaway speed within allowable IEC 60308 limits."
            ),
            recommendation=(
                "Ensure overspeed mechanical trip relay is set at 125% - 130% of synchronous speed."
            ),
            governing_principle="IEC 60308 Field Acceptance Tests for Hydraulic Turbine Governors"
        ))

    # 2. Water hammer pressure surge
    if sim.max_head_surge_pct > 25.0:
        insights.append(EngineeringObservation(
            category="Hydraulics",
            level="CRITICAL",
            title=f"Severe Water Hammer Pressure Surge (+{sim.max_head_surge_pct:.1f}%)",
            observation=(
                f"Peak transient head reached {sim.max_head_m:.1f} m (+{sim.max_head_surge_pct:.1f}% above baseline). "
                "Rapid deceleration of the penstock water column generated dangerous acoustic pressure shock waves."
            ),
            recommendation=(
                "Increase governor minimum gate closing time (prolong servomotor stroke time) to exceed "
                "the critical pipe reflection time (2L/a). Consider installing a surge tank or pressure relief valve (PRV)."
            ),
            governing_principle="Allievi & Joukowsky Water Hammer Surge Pressure Equations"
        ))
    elif sim.max_head_surge_pct > 10.0:
        insights.append(EngineeringObservation(
            category="Hydraulics",
            level="OPTIMIZATION",
            title=f"Controlled Pressure Surge (+{sim.max_head_surge_pct:.1f}%)",
            observation=(
                f"Transient head peak of {sim.max_head_m:.1f} m represents a manageable +{sim.max_head_surge_pct:.1f}% pressure surge."
            ),
            recommendation=(
                "Verify that penstock pipe pressure rating (nominal PN rating) includes adequate safety factor (SF ≥ 1.5)."
            ),
            governing_principle="Penstock Wall Thickness & Allowable Hoop Stress (σ = P·D / 2t)"
        ))

    # 3. Governor Settling Performance
    if sim.settling_time_s is not None and sim.settling_time_s > 0:
        insights.append(EngineeringObservation(
            category="Control Systems",
            level="INFO",
            title=f"System Settling Time: {sim.settling_time_s:.1f} seconds",
            observation=(
                f"The hydro governor returned grid frequency and runner speed to within ±2% tolerance "
                f"in {sim.settling_time_s:.1f} s following the transient event."
            ),
            recommendation=(
                "Governor parameters provide stable closed-loop damping without sustained hunting or oscillations."
            ),
            governing_principle="Control Loop Damping Ratio and Closed-Loop Stability Criteria"
        ))

    return insights
