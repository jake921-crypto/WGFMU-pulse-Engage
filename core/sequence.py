"""RRAM pulse sequence generation: LTP/LTD, retention, read_retention."""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from .units import parse_time_to_seconds

# Segment labels
LABEL_SET_WRITE = "SET_WRITE"
LABEL_RESET_WRITE = "RESET_WRITE"
LABEL_READ = "READ"
LABEL_HOLD = "HOLD"
LABEL_IDLE = "IDLE"
LABEL_FORMING = "FORMING"

# 전압 전환 시 같은 시간에 두 점이 겹치지 않도록, 구간 사이에 넣는 최소 시간.
# 상승(0→V)=rising time, 하강(V→0)=falling time. 1 ns.
RISE_TIME_S = 1e-9   # 1 ns (rising edge)
FALL_TIME_S = 1e-9  # 1 ns (falling edge)


def _transition_time(points: List, t: float, next_voltage: float) -> float:
    """이미 구간이 있으면 다음 구간 시작 전에 rising/falling time만큼 시간을 밀어줌.
    이전 구간 끝 전압이 next_voltage보다 크면 falling, 아니면 rising.
    """
    if not points:
        return t
    prev_voltage = points[-1][1]
    step = FALL_TIME_S if next_voltage < prev_voltage else RISE_TIME_S
    return t + step


def _append_segment(
    points: List[Tuple[float, float, str]],
    t_start: float,
    t_end: float,
    voltage: float,
    label: str,
) -> None:
    """Append step waveform segment: (t_start, V), (t_end, V)."""
    points.append((t_start, voltage, label))
    points.append((t_end, voltage, label))


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def _validate_non_negative(value: float, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")


@dataclass
class FormingConfig:
    """Optional forming / pre-conditioning pulse."""
    voltage_v: float
    width_s: float
    count: int = 1

    def __post_init__(self) -> None:
        _validate_positive(self.width_s, "width_s")
        if self.count < 0:
            raise ValueError("count must be non-negative")


@dataclass
class LTPLTDSettings:
    """Parameters for LTP (SET) + LTD (RESET). Sequence starts with optional initial hold + read, then write cycles."""
    # LTP (SET)
    v_write_set_v: float
    # LTD (RESET)
    v_write_reset_v: float
    # Common
    width_s: float
    interval_s: float
    v_read_v: float
    read_width_s: float
    cycles: int  # N: cycles per LTP and per LTD
    forming: Optional[FormingConfig] = None
    initial_holding_time_s: float = 0.0  # 초기 holding 후 첫 read

    def __post_init__(self) -> None:
        _validate_positive(self.width_s, "width_s")
        _validate_positive(self.interval_s, "interval_s")
        _validate_positive(self.read_width_s, "read_width_s")
        if self.cycles <= 0:
            raise ValueError("cycles must be positive")
        _validate_non_negative(self.initial_holding_time_s, "initial_holding_time_s")


def generate_ltp_ltd(settings: LTPLTDSettings) -> List[Tuple[float, float, str]]:
    """
    Order: [forming] → [initial hold] → initial read → interval →
    LTP phase: N × (SET write + interval + read + interval).
    LTD phase: N × (RESET write + interval + read + interval).
    """
    points: List[Tuple[float, float, str]] = []
    t = 0.0

    if settings.forming:
        for _ in range(settings.forming.count):
            t = _transition_time(points, t, settings.forming.voltage_v)
            _append_segment(
                points, t, t + settings.forming.width_s,
                settings.forming.voltage_v, LABEL_FORMING,
            )
            t += settings.forming.width_s
            t = _transition_time(points, t, 0.0)
            _append_segment(points, t, t + settings.interval_s, 0.0, LABEL_IDLE)
            t += settings.interval_s

    # 초기 holding (설정 시)
    if settings.initial_holding_time_s > 0:
        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + settings.initial_holding_time_s, 0.0, LABEL_HOLD)
        t += settings.initial_holding_time_s

    # 초기 read pulse (먼저 한 번 read)
    t = _transition_time(points, t, settings.v_read_v)
    _append_segment(
        points, t, t + settings.read_width_s,
        settings.v_read_v, LABEL_READ,
    )
    t += settings.read_width_s
    t = _transition_time(points, t, 0.0)
    _append_segment(points, t, t + settings.interval_s, 0.0, LABEL_IDLE)
    t += settings.interval_s

    # LTP (SET) phase
    for _ in range(settings.cycles):
        t = _transition_time(points, t, settings.v_write_set_v)
        _append_segment(
            points, t, t + settings.width_s,
            settings.v_write_set_v, LABEL_SET_WRITE,
        )
        t += settings.width_s
        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + settings.interval_s, 0.0, LABEL_IDLE)
        t += settings.interval_s
        t = _transition_time(points, t, settings.v_read_v)
        _append_segment(
            points, t, t + settings.read_width_s,
            settings.v_read_v, LABEL_READ,
        )
        t += settings.read_width_s
        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + settings.interval_s, 0.0, LABEL_IDLE)
        t += settings.interval_s

    # LTD (RESET) phase
    for _ in range(settings.cycles):
        t = _transition_time(points, t, settings.v_write_reset_v)
        _append_segment(
            points, t, t + settings.width_s,
            settings.v_write_reset_v, LABEL_RESET_WRITE,
        )
        t += settings.width_s
        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + settings.interval_s, 0.0, LABEL_IDLE)
        t += settings.interval_s
        t = _transition_time(points, t, settings.v_read_v)
        _append_segment(
            points, t, t + settings.read_width_s,
            settings.v_read_v, LABEL_READ,
        )
        t += settings.read_width_s
        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + settings.interval_s, 0.0, LABEL_IDLE)
        t += settings.interval_s

    return points


@dataclass
class RetentionSettings:
    """HRS/LRS retention: set or reset state -> hold -> read, for each holding time."""
    state: str  # "HRS" (reset) or "LRS" (set)
    v_set_v: float
    v_reset_v: float
    set_width_s: float
    reset_width_s: float
    holding_times_s: List[float]
    v_read_v: float
    read_width_s: float

    def __post_init__(self) -> None:
        if self.state not in ("HRS", "LRS"):
            raise ValueError("state must be 'HRS' or 'LRS'")
        _validate_positive(self.set_width_s, "set_width_s")
        _validate_positive(self.reset_width_s, "reset_width_s")
        _validate_positive(self.read_width_s, "read_width_s")
        if not self.holding_times_s:
            raise ValueError("holding_times_s must be non-empty")
        for i, ht in enumerate(self.holding_times_s):
            _validate_non_negative(ht, f"holding_times_s[{i}]")


def generate_retention(settings: RetentionSettings) -> List[Tuple[float, float, str]]:
    """
    For each holding time: (set or reset) -> hold -> read.
    """
    points: List[Tuple[float, float, str]] = []
    t = 0.0

    for hold_s in settings.holding_times_s:
        t = _transition_time(points, t, settings.v_set_v if settings.state == "LRS" else settings.v_reset_v)
        if settings.state == "LRS":
            _append_segment(
                points, t, t + settings.set_width_s,
                settings.v_set_v, LABEL_SET_WRITE,
            )
            t += settings.set_width_s
        else:
            _append_segment(
                points, t, t + settings.reset_width_s,
                settings.v_reset_v, LABEL_RESET_WRITE,
            )
            t += settings.reset_width_s

        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + hold_s, 0.0, LABEL_HOLD)
        t += hold_s
        t = _transition_time(points, t, settings.v_read_v)
        _append_segment(
            points, t, t + settings.read_width_s,
            settings.v_read_v, LABEL_READ,
        )
        t += settings.read_width_s
        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + 1e-6, 0.0, LABEL_IDLE)
        t += 1e-6

    return points


@dataclass
class ReadRetentionSettings:
    """Read-only retention: optional forming, then for each holding time hold -> (read × read_cycles)."""
    holding_times_s: List[float]
    v_read_v: float
    read_width_s: float
    read_cycles: int = 1  # 각 holding time마다 read 펄스 반복 횟수
    forming: Optional[FormingConfig] = None

    def __post_init__(self) -> None:
        if not self.holding_times_s:
            raise ValueError("holding_times_s must be non-empty")
        _validate_positive(self.read_width_s, "read_width_s")
        if self.read_cycles < 1:
            raise ValueError("read_cycles must be at least 1")
        for i, ht in enumerate(self.holding_times_s):
            _validate_non_negative(ht, f"holding_times_s[{i}]")


def generate_read_retention(settings: ReadRetentionSettings) -> List[Tuple[float, float, str]]:
    """Optional forming first, then for each holding time: hold -> read."""
    points: List[Tuple[float, float, str]] = []
    t = 0.0

    if settings.forming:
        for _ in range(settings.forming.count):
            t = _transition_time(points, t, settings.forming.voltage_v)
            _append_segment(
                points, t, t + settings.forming.width_s,
                settings.forming.voltage_v, LABEL_FORMING,
            )
            t += settings.forming.width_s
            t = _transition_time(points, t, 0.0)
            _append_segment(points, t, t + 1e-6, 0.0, LABEL_IDLE)
            t += 1e-6

    for hold_s in settings.holding_times_s:
        t = _transition_time(points, t, 0.0)
        _append_segment(points, t, t + hold_s, 0.0, LABEL_HOLD)
        t += hold_s
        for _ in range(settings.read_cycles):
            t = _transition_time(points, t, settings.v_read_v)
            _append_segment(
                points, t, t + settings.read_width_s,
                settings.v_read_v, LABEL_READ,
            )
            t += settings.read_width_s
            t = _transition_time(points, t, 0.0)
            _append_segment(points, t, t + 1e-6, 0.0, LABEL_IDLE)
            t += 1e-6

    return points


def generate_points(
    sequence_type: str,
    *,
    ltp_ltd: Optional[LTPLTDSettings] = None,
    retention: Optional[RetentionSettings] = None,
    read_retention: Optional[ReadRetentionSettings] = None,
) -> List[Tuple[float, float, str]]:
    """
    Dispatch to the appropriate generator.
    """
    if sequence_type == "ltp_ltd":
        if ltp_ltd is None:
            raise ValueError("ltp_ltd settings required")
        return generate_ltp_ltd(ltp_ltd)
    if sequence_type == "retention":
        if retention is None:
            raise ValueError("retention settings required")
        return generate_retention(retention)
    if sequence_type == "read_retention":
        if read_retention is None:
            raise ValueError("read_retention settings required")
        return generate_read_retention(read_retention)
    raise ValueError(f"Unknown sequence_type: {sequence_type}")
