"""Parse time strings: number + optional unit (s, m, u, n) -> seconds.
- 아무것도 안 붙이면 초(s), m=ms, u=µs, n=ns
"""
import re
from typing import Union

# 숫자 + 선택적 단위: 없음/s=초, m/ms=ms, u/us=µs, n/ns=ns. 대소문자 무시.
_TIME_PATTERN = re.compile(
    r"^\s*([+-]?(?:\d+\.?\d*|\.\d+))\s*([mun]s?|s)?\s*$",
    re.IGNORECASE,
)

# 단위 없음 또는 s -> 초, m/ms -> ms, u/us -> µs, n/ns -> ns
_SCALE = {
    "s": 1.0,
    "": 1.0,
    "m": 1e-3,
    "ms": 1e-3,
    "u": 1e-6,
    "us": 1e-6,
    "n": 1e-9,
    "ns": 1e-9,
}


def parse_time_to_seconds(value: Union[str, int, float]) -> float:
    """
    Parse a time value to seconds.
    - str: "100", "100s" -> 초, "100m" -> ms, "100u" -> µs, "100n" -> ns
    - int/float: interpreted as seconds.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        raise TypeError(f"Expected str, int, or float, got {type(value)}")
    s = value.strip()
    if not s:
        raise ValueError("Empty time string")
    m = _TIME_PATTERN.match(s)
    if not m:
        raise ValueError(f"Cannot parse time: {value!r}")
    num = float(m.group(1))
    unit = (m.group(2) or "").strip().lower()
    scale = _SCALE.get(unit)
    if scale is None:
        raise ValueError(f"Unknown time unit: {unit!r}. Use s, m, u, or n.")
    return num * scale
