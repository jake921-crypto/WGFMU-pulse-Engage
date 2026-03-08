"""Export time-voltage-segment data to CSV and Excel."""
from pathlib import Path
from typing import List, Tuple, Union, Any

import pandas as pd


def _points_to_df(points: Union[List[Tuple[float, float, str]], List[dict[str, Any]]]) -> pd.DataFrame:
    """Accept list of (time_s, voltage_v, segment_label) or list of dicts (e.g. WGFMU with extra columns)."""
    if not points:
        return pd.DataFrame(columns=["time_s", "voltage_v", "segment_label"])
    if isinstance(points[0], dict):
        return pd.DataFrame(points)
    return pd.DataFrame(
        points,
        columns=["time_s", "voltage_v", "segment_label"],
    )


def export_csv(
    points: Union[List[Tuple[float, float, str]], List[dict[str, Any]]],
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _points_to_df(points)
    df.to_csv(path, index=False, float_format="%.10e")


def export_xlsx(
    points: Union[List[Tuple[float, float, str]], List[dict[str, Any]]],
    path: str | Path,
    sheet_name: str = "Sequence",
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _points_to_df(points)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
