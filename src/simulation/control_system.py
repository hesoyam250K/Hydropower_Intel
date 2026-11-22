"""Hydropower speed and load governing control system.

Implements:
- PID speed governor with transient droop compensation.
- Servomotor rate limiters (preventing sudden destructive water hammer spikes).
- Gate position saturation (mechanical limits).
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class GovernorParams:
    """Hydro governor tuning parameters."""
    kp: float = 2.5  # Proportional gain
    ki: float = 0.5  # Integral gain
    kd: float = 0.1  # Derivative gain
    permanent_droop: float = 0.04  # Permanent speed droop R (typically 3-5%)
    max_gate_speed_per_sec: float = 0.15  # Max opening/closing rate (1/s)
    min_gate_position: float = 0.05  # Minimum idle opening
    max_gate_position: float = 1.00  # 100% full stroke


class HydroGovernor:
    """Electro-hydraulic speed governor simulation."""

    def __init__(self, params: GovernorParams = None, initial_gate: float = 0.80):
        self.params = params or GovernorParams()
        self.gate_position = max(
            self.params.min_gate_position,
            min(self.params.max_gate_position, initial_gate)
        )
        self.integral_error = 0.0
        self.prev_error = 0.0

    def reset(self, initial_gate: float = 0.80) -> None:
        self.gate_position = initial_gate
        self.integral_error = 0.0
        self.prev_error = 0.0

    def update(
        self,
        target_omega: float,
        current_omega: float,
        dt: float,
        is_auto: bool = True,
        manual_gate: float = 0.80
    ) -> float:
        """Calculates new gate position given speed error.

        In Automatic mode: adjusts gate to minimize speed error (omega_target - omega).
        In Manual mode: smoothly servos toward manual setpoint.
        """
        if dt <= 0:
            return self.gate_position

        if not is_auto:
            target_gate = max(self.params.min_gate_position, min(self.params.max_gate_position, manual_gate))
            error_gate = target_gate - self.gate_position
            max_delta = self.params.max_gate_speed_per_sec * dt
            delta_gate = max(-max_delta, min(max_delta, error_gate))
            self.gate_position += delta_gate
            return self.gate_position

        # Automatic speed regulation mode
        # Normalized speed deviation: e = (omega_0 - omega) / omega_0
        norm_error = (target_omega - current_omega) / max(1.0, target_omega)

        # Anti-windup clamped integration
        self.integral_error += norm_error * dt
        self.integral_error = max(-1.0, min(1.0, self.integral_error))

        # Derivative
        deriv_error = (norm_error - self.prev_error) / dt
        self.prev_error = norm_error

        # Control effort (desired gate change)
        u = (
            self.params.kp * norm_error
            + self.params.ki * self.integral_error
            + self.params.kd * deriv_error
        )

        desired_gate = self.gate_position + u * dt

        # Apply actuator speed limit (servo rate of travel)
        max_delta = self.params.max_gate_speed_per_sec * dt
        actual_delta = max(-max_delta, min(max_delta, desired_gate - self.gate_position))

        self.gate_position += actual_delta
        self.gate_position = max(
            self.params.min_gate_position,
            min(self.params.max_gate_position, self.gate_position)
        )

        return self.gate_position
