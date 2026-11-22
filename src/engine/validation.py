"""Input validation and physical boundaries for hydropower calculations."""

from dataclasses import dataclass
from typing import List, Optional, Tuple


class HydraulicValidationError(ValueError):
    """Raised when hydraulic parameters violate physical or operational limits."""
    pass


@dataclass
class ValidationResult:
    """Holds the result of a validation check with warnings and errors."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def validate_hydropower_inputs(
    flow_lps: Optional[float] = None,
    flow_m3s: Optional[float] = None,
    gross_head_m: Optional[float] = None,
    head_loss_m: Optional[float] = 0.0,
    efficiency: Optional[float] = 0.75,
    hours: Optional[float] = 24.0,
    pipe_diameter_m: Optional[float] = None,
    pipe_length_m: Optional[float] = None,
    roughness_mm: Optional[float] = None,
    c_factor: Optional[float] = None,
) -> ValidationResult:
    """Validates input parameters for hydraulic and electrical calculations.

    Ensures that values are within physically defensible boundaries.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Flow rate validation
    if flow_lps is not None:
        if flow_lps < 0:
            errors.append(f"Flow rate cannot be negative: {flow_lps} L/s provided.")
        elif flow_lps == 0:
            warnings.append("Flow rate is 0 L/s; power output will be zero.")
        elif flow_lps > 500000:
            warnings.append(f"Unusually large flow rate ({flow_lps:,.1f} L/s = {flow_lps/1000:,.1f} m³/s). Verify input units.")

    if flow_m3s is not None:
        if flow_m3s < 0:
            errors.append(f"Flow rate cannot be negative: {flow_m3s} m³/s provided.")
        elif flow_m3s == 0:
            warnings.append("Flow rate is 0 m³/s; power output will be zero.")
        elif flow_m3s > 500:
            warnings.append(f"Unusually large flow rate ({flow_m3s:,.1f} m³/s). Verify input units.")

    # 2. Gross head validation
    if gross_head_m is not None:
        if gross_head_m < 0:
            errors.append(f"Gross head cannot be negative: {gross_head_m} m provided.")
        elif gross_head_m == 0:
            warnings.append("Gross head is 0 m; no hydraulic potential energy is available.")
        elif gross_head_m > 2500:
            warnings.append(f"Gross head {gross_head_m} m exceeds highest commercial head plants (e.g. Bieudron ~1883 m).")

    # 3. Head loss validation
    if head_loss_m is not None:
        if head_loss_m < 0:
            errors.append(f"Head loss cannot be negative: {head_loss_m} m provided.")
        elif gross_head_m is not None and gross_head_m > 0:
            if head_loss_m >= gross_head_m:
                errors.append(
                    f"Head loss ({head_loss_m:.2f} m) meets or exceeds gross head ({gross_head_m:.2f} m). "
                    "Net head cannot be zero or negative."
                )
            elif head_loss_m > 0.20 * gross_head_m:
                warnings.append(
                    f"Head loss ({head_loss_m:.2f} m) exceeds 20% of gross head. "
                    "High hydraulic friction losses will substantially diminish plant economics."
                )

    # 4. Efficiency validation
    if efficiency is not None:
        if not (0.0 <= efficiency <= 1.0):
            errors.append(f"Overall efficiency must be between 0.0 and 1.0 (or 0% to 100%): {efficiency} provided.")
        elif efficiency > 0.95:
            warnings.append(
                f"Efficiency of {efficiency*100:.1f}% is exceptionally high. "
                "Typical modern water-to-wire efficiencies range from 75% to 92%."
            )
        elif efficiency < 0.40 and efficiency > 0.0:
            warnings.append(
                f"Efficiency of {efficiency*100:.1f}% is unusually low. "
                "Check for mechanical or hydraulic mismatches."
            )

    # 5. Operating hours validation
    if hours is not None:
        if hours < 0:
            errors.append(f"Operating duration cannot be negative: {hours} hours provided.")
        elif hours > 87600:  # 10 years
            warnings.append(f"Operating duration of {hours} hours exceeds typical planning horizons.")

    # 6. Pipe dimensions validation (if supplied)
    if pipe_diameter_m is not None:
        if pipe_diameter_m <= 0:
            errors.append(f"Internal pipe diameter must be strictly positive: {pipe_diameter_m} m provided.")
        elif pipe_diameter_m < 0.02:
            warnings.append(f"Pipe diameter {pipe_diameter_m*1000:.0f} mm is very small for hydropower penstocks.")
        elif pipe_diameter_m > 12.0:
            warnings.append(f"Pipe diameter {pipe_diameter_m:.2f} m is exceptionally large.")

    if pipe_length_m is not None:
        if pipe_length_m <= 0:
            errors.append(f"Pipe length must be strictly positive: {pipe_length_m} m provided.")
        elif pipe_length_m > 50000:
            warnings.append(f"Pipe length {pipe_length_m/1000:.1f} km is very long; verify penstock vs tunnel route.")

    if roughness_mm is not None:
        if roughness_mm < 0:
            errors.append(f"Pipe roughness cannot be negative: {roughness_mm} mm provided.")
        elif roughness_mm > 50:
            warnings.append(f"Roughness of {roughness_mm} mm indicates heavily deteriorated or corrugated lining.")

    if c_factor is not None:
        if c_factor <= 0:
            errors.append(f"Hazen-Williams C coefficient must be strictly positive: {c_factor} provided.")
        elif c_factor > 160:
            warnings.append(f"Hazen-Williams C factor {c_factor} is unusually high (smooth plastic is typically 150).")
        elif c_factor < 60:
            warnings.append(f"Hazen-Williams C factor {c_factor} indicates extreme tuburculation/deterioration.")

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
