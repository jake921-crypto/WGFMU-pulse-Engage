"""CLI: YAML config -> time-voltage CSV (and optional xlsx, preview)."""
from pathlib import Path
from datetime import datetime

import typer
import yaml

from core.schema import ConfigSchema
from core.sequence import (
    LTPLTDSettings,
    FormingConfig,
    RetentionSettings,
    ReadRetentionSettings,
)
from core.sequence_registry import generate_points
from core.models import WGFMUGateSweepPIVParams
from core.export import export_csv, export_xlsx

app = typer.Typer(help="RRAM pulse sequence generator (YAML -> CSV/xlsx)")


def _config_to_settings(cfg: ConfigSchema):
    """Build core settings from validated YAML config."""
    st = cfg.sequence_type
    if st == "ltp_ltd":
        if not cfg.ltp_ltd:
            raise typer.BadParameter("ltp_ltd section required for sequence_type=ltp_ltd")
        L = cfg.ltp_ltd
        forming = None
        if L.forming:
            forming = FormingConfig(
                voltage_v=L.forming.voltage_v,
                width_s=L.forming.width,
                count=L.forming.count,
            )
        return generate_points(
            "ltp_ltd",
            ltp_ltd=LTPLTDSettings(
                v_write_set_v=L.v_write_set_v,
                v_write_reset_v=L.v_write_reset_v,
                width_s=L.width,
                interval_s=L.interval,
                v_read_v=L.v_read_v,
                read_width_s=L.read_width,
                cycles=L.cycles,
                forming=forming,
                initial_holding_time_s=L.initial_holding_time,
            ),
        )
    if st == "retention":
        if not cfg.retention:
            raise typer.BadParameter("retention section required for sequence_type=retention")
        R = cfg.retention
        return generate_points(
            "retention",
            retention=RetentionSettings(
                state=R.state,
                v_set_v=R.v_set_v,
                v_reset_v=R.v_reset_v,
                set_width_s=R.set_width,
                reset_width_s=R.reset_width,
                holding_times_s=R.holding_times,
                v_read_v=R.v_read_v,
                read_width_s=R.read_width,
            ),
        )
    if st == "read_retention":
        if not cfg.read_retention:
            raise typer.BadParameter("read_retention section required for sequence_type=read_retention")
        RR = cfg.read_retention
        forming = None
        if RR.forming:
            forming = FormingConfig(
                voltage_v=RR.forming.voltage_v,
                width_s=RR.forming.width,
                count=RR.forming.count,
            )
        return generate_points(
            "read_retention",
            read_retention=ReadRetentionSettings(
                holding_times_s=RR.holding_times,
                v_read_v=RR.v_read_v,
                read_width_s=RR.read_width,
                read_cycles=getattr(RR, "read_cycles", 1),
                forming=forming,
            ),
        )
    if st == "wgfm_gate_sweep_piv":
        if not cfg.wgfm_gate_sweep_piv:
            raise typer.BadParameter("wgfm_gate_sweep_piv section required")
        W = cfg.wgfm_gate_sweep_piv
        params = WGFMUGateSweepPIVParams(
            start_v=W.start_v,
            stop_v=W.stop_v,
            step_v=W.step_v,
            sweep_mode=W.sweep_mode,
            base_v=W.base_v,
            off_time=W.off_time,
            rise_time=W.rise_time,
            pulse_width=W.pulse_width,
            fall_time=W.fall_time,
            measure_center_ratio=W.measure_center_ratio,
            interval_ratio=W.interval_ratio,
            average_ratio=W.average_ratio,
            use_vhold=W.use_vhold,
            vhold_v=W.vhold_v,
            duplicate_endpoint=W.duplicate_endpoint,
        )
        return generate_points("wgfm_gate_sweep_piv", wgfm_gate_sweep_piv=params)
    raise typer.BadParameter(f"Unknown sequence_type: {st}")


def _plot_preview(points: list, title: str = "Pulse sequence") -> None:
    """Downsample long sequences for display."""
    import matplotlib.pyplot as plt
    import numpy as np

    if not points:
        plt.figure()
        plt.title(title)
        plt.show()
        return

    if isinstance(points[0], dict):
        times = np.array([p["time_s"] for p in points])
        volts = np.array([p["voltage_v"] for p in points])
    else:
        times = np.array([p[0] for p in points])
        volts = np.array([p[1] for p in points])
    n = len(times)
    max_pts = 20_000
    if n > max_pts:
        step = max(1, n // max_pts)
        idx = np.arange(0, n, step)
        if idx[-1] != n - 1:
            idx = np.r_[idx, n - 1]
        times = times[idx]
        volts = volts[idx]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.step(times, volts, where="post", color="steelblue")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


@app.command()
def main(
    config: Path = typer.Argument(..., help="Path to YAML config file"),
    output: Path = typer.Option(None, "--output", "-o", help="Output CSV path (default: auto)"),
    xlsx: bool = typer.Option(False, "--xlsx", help="Also write Excel file"),
    preview: bool = typer.Option(False, "--preview", help="Show waveform plot"),
) -> None:
    """Generate time-voltage CSV from YAML config."""
    if not config.exists():
        typer.echo(f"Error: config file not found: {config}", err=True)
        raise typer.Exit(1)

    with open(config, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        typer.echo("Error: empty YAML", err=True)
        raise typer.Exit(1)

    try:
        cfg = ConfigSchema.model_validate(data)
    except Exception as e:
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(1)

    try:
        points = _config_to_settings(cfg)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    if not output:
        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = cfg.sequence_type
        output = Path(f"{key}_{date}.csv")

    export_csv(points, output)
    typer.echo(f"Wrote {output}")

    if xlsx:
        xpath = output.with_suffix(".xlsx")
        export_xlsx(points, xpath, sheet_name=cfg.sequence_type)
        typer.echo(f"Wrote {xpath}")

    if preview:
        _plot_preview(points, title=f"Sequence: {cfg.sequence_type}")


if __name__ == "__main__":
    app()
