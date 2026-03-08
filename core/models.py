"""Pydantic models for sequence parameters (e.g. WGFMU)."""
from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from .units import parse_time_to_seconds


def _parse_time(v: Union[str, int, float]) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return parse_time_to_seconds(v)


class WGFMUGateSweepPIVParams(BaseModel):
    """WGFMU gate sweep + PIV on-time measurement sequence parameters."""

    start_v: float
    stop_v: float
    step_v: float = Field(..., gt=0)
    sweep_mode: Literal["forward", "reverse", "double"] = "forward"
    base_v: float = 0.0
    off_time: Union[str, float] = 0.0
    rise_time: Union[str, float] = 0.0
    pulse_width: Union[str, float]
    fall_time: Union[str, float] = 0.0
    measure_center_ratio: float = Field(0.50, ge=0, le=1)
    interval_ratio: float = Field(0.40, ge=0, le=1)
    average_ratio: float = Field(0.30, ge=0, le=1)
    use_vhold: bool = False
    vhold_v: float = 0.0
    duplicate_endpoint: bool = True

    @field_validator("off_time", "rise_time", "pulse_width", "fall_time", mode="before")
    @classmethod
    def time_to_seconds(cls, v):
        if v is None:
            return v
        return _parse_time(v) if isinstance(v, str) else float(v)

    @property
    def off_time_s(self) -> float:
        return float(self.off_time)

    @property
    def rise_time_s(self) -> float:
        return float(self.rise_time)

    @property
    def pulse_width_s(self) -> float:
        return float(self.pulse_width)

    @property
    def fall_time_s(self) -> float:
        return float(self.fall_time)

    @model_validator(mode="after")
    def start_stop_differ(self):
        if self.start_v == self.stop_v:
            raise ValueError("start_v and stop_v must differ")
        return self
