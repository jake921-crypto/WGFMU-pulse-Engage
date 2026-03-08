"""Registry of sequence types and generators."""
from typing import List, Any, Callable

SEQUENCE_TYPES = [
    "ltp_ltd",
    "retention",
    "read_retention",
    "wgfm_gate_sweep_piv",
]


def generate_points(
    sequence_type: str,
    *,
    ltp_ltd=None,
    retention=None,
    read_retention=None,
    wgfm_gate_sweep_piv=None,
) -> Any:
    """
    Dispatch to the appropriate generator.
    Returns list of (time_s, voltage_v, segment_label) or list of dicts for WGFMU.
    """
    if sequence_type == "ltp_ltd":
        if ltp_ltd is None:
            raise ValueError("ltp_ltd settings required")
        from .sequence import generate_ltp_ltd
        return generate_ltp_ltd(ltp_ltd)
    if sequence_type == "retention":
        if retention is None:
            raise ValueError("retention settings required")
        from .sequence import generate_retention
        return generate_retention(retention)
    if sequence_type == "read_retention":
        if read_retention is None:
            raise ValueError("read_retention settings required")
        from .sequence import generate_read_retention
        return generate_read_retention(read_retention)
    if sequence_type == "wgfm_gate_sweep_piv":
        if wgfm_gate_sweep_piv is None:
            raise ValueError("wgfm_gate_sweep_piv settings required")
        from .sequences import generate_wgfm_gate_sweep_piv
        return generate_wgfm_gate_sweep_piv(wgfm_gate_sweep_piv)
    raise ValueError(f"Unknown sequence_type: {sequence_type!r}")
