"""Keysight B1500A WGFMU Pattern Editor: gate voltage sweep + PIV on-time measurement."""
from typing import List, Dict, Any

from ..units import parse_time_to_seconds
from ..models import WGFMUGateSweepPIVParams

# Segment labels (4 segments per voltage point)
LABEL_OFF = "OFF"
LABEL_RISE = "RISE"
LABEL_PULSE = "PULSE"
LABEL_FALL = "FALL"

# Minimal step between segments (avoid same-timestamp)
TRANSITION_S = 1e-9


def _voltage_list(params: Any) -> List[float]:
    """Build voltage list; index-based to avoid float accumulation."""
    delta = params.stop_v - params.start_v
    num_points = round(abs(delta) / params.step_v) + 1
    if num_points < 1:
        num_points = 1
    step_signed = delta / (num_points - 1) if num_points > 1 else 0.0
    forward = [params.start_v + i * step_signed for i in range(num_points)]

    if params.sweep_mode == "forward":
        return forward
    if params.sweep_mode == "reverse":
        return list(reversed(forward))
    # double: forward then reverse; duplicate_endpoint=True -> don't repeat turn point
    if params.duplicate_endpoint:
        return forward + list(reversed(forward))[1:]
    return forward + list(reversed(forward))


def generate_wgfm_gate_sweep_piv(params: Any) -> List[Dict[str, Any]]:
    """
    Generate step waveform table: each V_i gets OFF -> RISE -> PULSE -> FALL.
    Each row is a dict with time_s, voltage_v, segment_label and WGFMU columns.
    """
    voltages = _voltage_list(params)
    base = params.base_v if not params.use_vhold else params.vhold_v
    rows: List[Dict[str, Any]] = []
    t = 0.0

    for point_index, v_i in enumerate(voltages):
        # Determine sweep direction for this point (for double: first half forward, second half reverse)
        if params.sweep_mode == "forward":
            sweep_direction = "forward"
        elif params.sweep_mode == "reverse":
            sweep_direction = "reverse"
        else:
            n_fwd = round(abs(params.stop_v - params.start_v) / params.step_v) + 1
            sweep_direction = "forward" if point_index < n_fwd else "reverse"

        # PIV: pulse_start_time = time at start of PULSE (end of RISE)
        t_off_end = t + max(params.off_time_s, TRANSITION_S)
        t_rise_end = t_off_end + TRANSITION_S + max(params.rise_time_s, TRANSITION_S)
        pulse_start_time = t_rise_end + TRANSITION_S  # start of PULSE
        measure_center_s = pulse_start_time + params.pulse_width_s * params.measure_center_ratio
        interval_s = params.pulse_width_s * params.interval_ratio
        average_s = params.pulse_width_s * params.average_ratio
        measure_start_s = measure_center_s - interval_s / 2
        measure_end_s = measure_center_s + interval_s / 2

        piv = {
            "measure_center_s": measure_center_s,
            "interval_s": interval_s,
            "average_s": average_s,
            "measure_start_s": measure_start_s,
            "measure_end_s": measure_end_s,
            "point_index": point_index,
            "sweep_direction": sweep_direction,
        }

        # OFF (minimal step before new point if not first)
        if rows:
            t += TRANSITION_S
        t_end_off = t + max(params.off_time_s, TRANSITION_S)
        rows.append({"time_s": t, "voltage_v": base, "segment_label": LABEL_OFF, **piv})
        rows.append({"time_s": t_end_off, "voltage_v": base, "segment_label": LABEL_OFF, **piv})
        t = t_end_off

        # RISE
        t += TRANSITION_S
        t_end_rise = t + max(params.rise_time_s, TRANSITION_S)
        rows.append({"time_s": t, "voltage_v": v_i, "segment_label": LABEL_RISE, **piv})
        rows.append({"time_s": t_end_rise, "voltage_v": v_i, "segment_label": LABEL_RISE, **piv})
        t = t_end_rise

        # PULSE (pulse_width always > 0)
        t += TRANSITION_S
        rows.append({"time_s": t, "voltage_v": v_i, "segment_label": LABEL_PULSE, **piv})
        t += params.pulse_width_s
        rows.append({"time_s": t, "voltage_v": v_i, "segment_label": LABEL_PULSE, **piv})

        # FALL
        t += TRANSITION_S
        t_end_fall = t + max(params.fall_time_s, TRANSITION_S)
        rows.append({"time_s": t, "voltage_v": base, "segment_label": LABEL_FALL, **piv})
        rows.append({"time_s": t_end_fall, "voltage_v": base, "segment_label": LABEL_FALL, **piv})
        t = t_end_fall

    return rows
