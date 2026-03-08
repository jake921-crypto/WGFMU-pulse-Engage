"""Pydantic schema for YAML config (CLI)."""
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from .units import parse_time_to_seconds


def _parse_time(v: Union[str, int, float]) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return parse_time_to_seconds(v)


class FormingSchema(BaseModel):
    voltage_v: float
    width: Union[str, float]
    count: int = 1

    @field_validator("width", mode="before")
    @classmethod
    def width_to_seconds(cls, v):
        return _parse_time(v) if isinstance(v, str) else float(v)


class LTPLTDSchema(BaseModel):
    v_write_set_v: float
    v_write_reset_v: float
    width: Union[str, float]
    interval: Union[str, float]
    v_read_v: float
    read_width: Union[str, float]
    cycles: int = Field(..., gt=0)
    forming: Optional[FormingSchema] = None
    initial_holding_time: Union[str, float] = 0.0

    @field_validator("width", "interval", "read_width", mode="before")
    @classmethod
    def time_to_seconds(cls, v):
        if v is None:
            return v
        return _parse_time(v) if isinstance(v, str) else float(v)

    @field_validator("initial_holding_time", mode="before")
    @classmethod
    def initial_holding_to_seconds(cls, v):
        if v is None or v == "":
            return 0.0
        return _parse_time(v) if isinstance(v, str) else float(v)


class RetentionSchema(BaseModel):
    state: str = Field(..., pattern="^(HRS|LRS)$")
    v_set_v: float
    v_reset_v: float
    set_width: Union[str, float]
    reset_width: Union[str, float]
    holding_times: List[Union[str, float]]
    v_read_v: float
    read_width: Union[str, float]

    @field_validator("set_width", "reset_width", "read_width", mode="before")
    @classmethod
    def time_to_seconds(cls, v):
        if v is None:
            return v
        return _parse_time(v) if isinstance(v, str) else float(v)

    @field_validator("holding_times", mode="before")
    @classmethod
    def holding_times_to_seconds(cls, v):
        if not v:
            return v
        return [_parse_time(x) if isinstance(x, str) else float(x) for x in v]


class ReadRetentionSchema(BaseModel):
    holding_times: List[Union[str, float]]
    v_read_v: float
    read_width: Union[str, float]
    read_cycles: int = 1
    forming: Optional[FormingSchema] = None

    @field_validator("read_width", mode="before")
    @classmethod
    def time_to_seconds(cls, v):
        if v is None:
            return v
        return _parse_time(v) if isinstance(v, str) else float(v)

    @field_validator("holding_times", mode="before")
    @classmethod
    def holding_times_to_seconds(cls, v):
        if not v:
            return v
        return [_parse_time(x) if isinstance(x, str) else float(x) for x in v]


class WGFMGateSweepPIVSchema(BaseModel):
    start_v: float
    stop_v: float
    step_v: float = Field(..., gt=0)
    sweep_mode: str = Field("forward", pattern="^(forward|reverse|double)$")
    base_v: float = 0.0
    off_time: Union[str, float] = 0.0
    rise_time: Union[str, float] = 0.0
    pulse_width: Union[str, float]
    fall_time: Union[str, float] = 0.0
    measure_center_ratio: float = 0.50
    interval_ratio: float = 0.40
    average_ratio: float = 0.30
    use_vhold: bool = False
    vhold_v: float = 0.0
    duplicate_endpoint: bool = True

    @field_validator("off_time", "rise_time", "pulse_width", "fall_time", mode="before")
    @classmethod
    def time_to_seconds(cls, v):
        if v is None:
            return v
        return _parse_time(v) if isinstance(v, str) else float(v)


class ConfigSchema(BaseModel):
    sequence_type: str = Field(
        ...,
        pattern="^(ltp_ltd|retention|read_retention|wgfm_gate_sweep_piv)$",
    )
    ltp_ltd: Optional[LTPLTDSchema] = None
    retention: Optional[RetentionSchema] = None
    read_retention: Optional[ReadRetentionSchema] = None
    wgfm_gate_sweep_piv: Optional[WGFMGateSweepPIVSchema] = None
