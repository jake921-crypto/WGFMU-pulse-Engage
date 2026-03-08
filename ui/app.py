"""PySide6 GUI for RRAM pulse sequence generator."""
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QLabel,
    QPushButton,
    QGroupBox,
    QStackedWidget,
    QMessageBox,
    QFileDialog,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt
import numpy as np

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.sequence import (
    LTPLTDSettings,
    FormingConfig,
    RetentionSettings,
    ReadRetentionSettings,
    generate_ltp_ltd,
    generate_retention,
    generate_read_retention,
)
from core.sequence_registry import generate_points
from core.models import WGFMUGateSweepPIVParams
from core.units import parse_time_to_seconds
from core.export import export_csv, export_xlsx

# Matplotlib embedded in Qt
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Default log-scale holding times (seconds)
DEFAULT_HOLDING_TIMES = [1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1, 3, 10]
MAX_PLOT_POINTS = 20_000


def _points_to_tsv_time_voltage_only(points: list) -> str:
    """time_s, voltage_v 숫자만 탭 구분 문자열로 (헤더·segment_label 제외)."""
    if points and isinstance(points[0], dict):
        return "\n".join(f"{p['time_s']:.10e}\t{p['voltage_v']:.10e}" for p in points)
    return "\n".join(f"{t:.10e}\t{v:.10e}" for t, v, _ in points)


class TableViewDialog(QDialog):
    """펄스 데이터 테이블 표시 및 복사용 대화상자."""

    def __init__(self, points, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pulse table (copy to Excel)")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)

        is_dict = points and isinstance(points[0], dict)
        if is_dict:
            columns = list(points[0].keys())
            # measurement_center 옆에 measurement_point 칸 추가 (1로 고정)
            if "measure_center_s" in columns:
                idx_mc = columns.index("measure_center_s")
                columns.insert(idx_mc + 1, "measurement_point")
            n_cols = len(columns)
            self.table = QTableWidget(len(points) + 1, n_cols)
            self.table.setHorizontalHeaderLabels(columns)
            for col, key in enumerate(columns):
                self.table.setItem(0, col, QTableWidgetItem(key))
            for row, p in enumerate(points, start=1):
                for col, key in enumerate(columns):
                    if key == "measurement_point":
                        self.table.setItem(row, col, QTableWidgetItem("1"))
                        continue
                    val = p.get(key)
                    if isinstance(val, float):
                        self.table.setItem(row, col, QTableWidgetItem(f"{val:.10e}"))
                    else:
                        self.table.setItem(row, col, QTableWidgetItem(str(val)))
        else:
            # 2-terminal: pulse + measure_center_s(ratio 0.5), measurement_point(1), interval_s(0.4), average_s(0.3), measure_end_s
            cols_2term = ["time_s", "voltage_v", "segment_label", "measure_center_s", "measurement_point", "interval_s", "average_s", "measure_end_s"]
            n_cols = len(cols_2term)
            self.table = QTableWidget(len(points) + 1, n_cols)
            self.table.setHorizontalHeaderLabels(cols_2term)
            for col, val in enumerate(cols_2term):
                self.table.setItem(0, col, QTableWidgetItem(val))
            # segment = 연속 두 행. measurement는 READ 구간에만 (ratio 0.5, 0.4, 0.3)
            seg_meas = {}  # row_start_index -> (mc, interval_s, avg_s, me_end)
            for i in range(0, len(points) - 1, 2):
                t1, v1, l1 = points[i]
                t2, v2, l2 = points[i + 1]
                if l1 == l2 and v1 == v2 and l1 == "READ":
                    duration = t2 - t1
                    mc = t1 + duration * 0.5
                    interval_s = duration * 0.4
                    avg_s = duration * 0.3
                    me_end = mc + interval_s / 2
                    seg_meas[i] = (mc, interval_s, avg_s, me_end)
            for row, idx in enumerate(range(len(points)), start=1):
                t, v, label = points[idx]
                self.table.setItem(row, 0, QTableWidgetItem(f"{t:.10e}"))
                self.table.setItem(row, 1, QTableWidgetItem(f"{v:.10e}"))
                self.table.setItem(row, 2, QTableWidgetItem(label))
                start_idx = (idx // 2) * 2
                if start_idx in seg_meas:
                    mc, interval_s, avg_s, me_end = seg_meas[start_idx]
                    self.table.setItem(row, 3, QTableWidgetItem(f"{mc:.10e}"))
                    self.table.setItem(row, 4, QTableWidgetItem("1"))
                    self.table.setItem(row, 5, QTableWidgetItem(f"{interval_s:.10e}"))
                    self.table.setItem(row, 6, QTableWidgetItem(f"{avg_s:.10e}"))
                    self.table.setItem(row, 7, QTableWidgetItem(f"{me_end:.10e}"))
                else:
                    for c in range(3, n_cols):
                        self.table.setItem(row, c, QTableWidgetItem(""))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_copy_pulse = QPushButton("Copy pulse")
        btn_copy_pulse.clicked.connect(self._copy_pulse)
        btn_row.addWidget(btn_copy_pulse)
        btn_copy_meas = QPushButton("Copy measuring time")
        btn_copy_meas.clicked.connect(self._copy_measuring_time)
        btn_row.addWidget(btn_copy_meas)
        layout.addLayout(btn_row)

        self._points = points
        self._is_dict = is_dict

    def _copy_pulse(self) -> None:
        text = _points_to_tsv_time_voltage_only(self._points)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "time_s, voltage_v copied to clipboard.")

    def _copy_measuring_time(self) -> None:
        """measure_center_s, measurement_point(1), interval_s, average_s 4칸 숫자 복사 (헤더 없음)."""
        if not self._points:
            return
        if isinstance(self._points[0], dict):
            # 3-terminal (TFT Gate Sweep): point_index당 한 행
            keys = ["measure_center_s", "interval_s", "average_s"]
            seen = set()
            lines = []
            for p in self._points:
                point_index = p.get("point_index")
                if point_index is not None and point_index not in seen:
                    seen.add(point_index)
                    vals = [p.get(k) for k in keys]
                    if all(v is not None for v in vals):
                        line_vals = [vals[0], 1, vals[1], vals[2]]
                        lines.append("\t".join(f"{v:.10e}" if isinstance(v, float) else str(v) for v in line_vals))
            if not lines:
                QMessageBox.information(self, "Copy", "No measuring time data in this table.")
                return
            QApplication.clipboard().setText("\n".join(lines))
        else:
            # 2-terminal: READ segment당 한 행 (ratio 0.5, 0.4, 0.3)
            lines = []
            for i in range(0, len(self._points) - 1, 2):
                t1, v1, l1 = self._points[i]
                t2, v2, l2 = self._points[i + 1]
                if l1 == l2 and v1 == v2 and l1 == "READ":
                    duration = t2 - t1
                    mc = t1 + duration * 0.5
                    interval_s = duration * 0.4
                    avg_s = duration * 0.3
                    line_vals = [mc, 1, interval_s, avg_s]
                    lines.append("\t".join(f"{v:.10e}" if isinstance(v, float) else str(v) for v in line_vals))
            if not lines:
                QMessageBox.information(self, "Copy", "No segment data for measuring time.")
                return
            QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Copy", "measure_center_s, measurement_point, interval_s, average_s copied.")


def _parse_float(s: str, name: str) -> float:
    s = s.strip()
    if not s:
        raise ValueError(f"{name} is empty")
    try:
        return float(s)
    except ValueError:
        return parse_time_to_seconds(s)


def _parse_holding_times(s: str) -> List[float]:
    """Parse comma or space separated numbers or time strings."""
    s = s.strip()
    if not s:
        return []
    parts = [p.strip() for p in s.replace(",", " ").split() if p.strip()]
    out = []
    for p in parts:
        try:
            out.append(float(p))
        except ValueError:
            out.append(parse_time_to_seconds(p))
    return out


class PlotWidget(QWidget):
    """Matplotlib canvas with downsampling for long sequences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(10, 3))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def plot_points(
        self,
        points,
        downsample: bool = True,
    ) -> None:
        self.ax.clear()
        if not points:
            self.ax.set_title("No data")
            self.canvas.draw()
            return
        if isinstance(points[0], dict):
            times = np.array([p["time_s"] for p in points])
            volts = np.array([p["voltage_v"] for p in points])
        else:
            times = np.array([p[0] for p in points])
            volts = np.array([p[1] for p in points])
        n = len(times)
        if downsample and n > MAX_PLOT_POINTS:
            step = max(1, n // MAX_PLOT_POINTS)
            idx = np.arange(0, n, step)
            if idx[-1] != n - 1:
                idx = np.r_[idx, n - 1]
            times = times[idx]
            volts = volts[idx]
        self.ax.step(times, volts, where="post", color="steelblue")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.set_title("Pulse sequence (preview)")
        self.ax.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pulse Sequence Generator  V1.0  Producer : Jae Jun Lee")
        self.setMinimumWidth(700)
        self.setMinimumHeight(650)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Producer's Note (클릭하면 펼쳐짐)
        note_grp = QGroupBox("Producer's Note")
        note_grp.setCheckable(True)
        note_grp.setChecked(False)
        note_text_ko = (
            "1500 상의 WGFMU의 펄스 설정이 귀찮고 엑셀에 하나하나 설정해야 하는 번거로움이 있어, "
            "이를 조금이라도 덜고자 프로그램을 간단하게 제작해봤습니다. "
            "사용하시다 추가하고 싶은 펄스 계형이나 개선점 있으면 연락주세요.  -이재준 드림-"
        )
        note_text_en = (
            "Setting up pulses for the B1500 WGFMU was tedious, and having to configure everything "
            "one by one in Excel was cumbersome. This program was made to ease that a little. "
            "If you have pulse patterns you’d like to add or any suggestions, please get in touch.  — Jae Jun Lee"
        )
        note_label = QLabel(note_text_ko + "\n\n" + note_text_en)
        note_label.setWordWrap(True)
        note_label.setStyleSheet("color: #e65100; padding: 6px;")  # 주황색
        note_layout = QVBoxLayout(note_grp)
        note_layout.addWidget(note_label)
        note_label.setVisible(False)
        note_grp.toggled.connect(note_label.setVisible)
        layout.addWidget(note_grp)

        # Terminal type + Sequence type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Terminal:"))
        self.terminal_type = QComboBox()
        self.terminal_type.addItems(["2 terminal", "3 terminal"])
        self.terminal_type.currentIndexChanged.connect(self._on_terminal_changed)
        type_layout.addWidget(self.terminal_type)
        type_layout.addWidget(QLabel("Sequence:"))
        self.seq_type = QComboBox()
        self._seq_items_2term = ["LTP/LTD", "Retention (HRS/LRS)", "Read retention"]
        self._seq_items_3term = ["TFT Gate Sweep"]
        self.seq_type.addItems(self._seq_items_2term)
        self.seq_type.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.seq_type)
        layout.addLayout(type_layout)
        # Time unit hint
        layout.addWidget(QLabel("시간 단위: 숫자만 또는 s=초, m=ms, u=µs, n=ns (예: 100, 100u, 1m)"))

        # Stacked parameter forms
        self.forms = QStackedWidget()
        self.form_ltp_ltd = self._build_ltp_ltd_form()
        self.form_retention = self._build_retention_form()
        self.form_read_ret = self._build_read_retention_form()
        self.form_wgfm = self._build_wgfm_form()
        self.forms.addWidget(self.form_ltp_ltd)
        self.forms.addWidget(self.form_retention)
        self.forms.addWidget(self.form_read_ret)
        self.forms.addWidget(self.form_wgfm)
        layout.addWidget(self.forms)

        # Preview
        preview_grp = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_grp)
        self.downsample_cb = QCheckBox("Downsample long sequences for plot")
        self.downsample_cb.setChecked(True)
        preview_layout.addWidget(self.downsample_cb)
        self.plot_widget = PlotWidget()
        preview_layout.addWidget(self.plot_widget)
        layout.addWidget(preview_grp)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_preview = QPushButton("Update preview")
        self.btn_preview.clicked.connect(self._update_preview)
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_xlsx = QPushButton("Export Excel (xlsx)")
        self.btn_export_xlsx.clicked.connect(self._export_xlsx)
        self.btn_show_table = QPushButton("Show table (copy to Excel)")
        self.btn_show_table.clicked.connect(self._show_table)
        btn_layout.addWidget(self.btn_preview)
        btn_layout.addWidget(self.btn_export_csv)
        btn_layout.addWidget(self.btn_export_xlsx)
        btn_layout.addWidget(self.btn_show_table)
        layout.addLayout(btn_layout)

        self._on_terminal_changed(0)

    def _build_ltp_ltd_form(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        self.le_v_set = QLineEdit()
        fl.addRow("V_write SET (V):", self.le_v_set)
        self.le_v_reset = QLineEdit()
        fl.addRow("V_write RESET (V):", self.le_v_reset)
        self.le_width = QLineEdit()
        fl.addRow("Write width:", self.le_width)
        self.le_interval = QLineEdit()
        fl.addRow("Interval:", self.le_interval)
        self.le_v_read = QLineEdit()
        fl.addRow("V_read (V):", self.le_v_read)
        self.le_read_width = QLineEdit()
        fl.addRow("Read width:", self.le_read_width)
        self.le_initial_holding = QLineEdit()
        fl.addRow("Initial holding time:", self.le_initial_holding)
        self.spin_cycles = QSpinBox()
        self.spin_cycles.setRange(0, 100000)
        self.spin_cycles.setValue(0)
        fl.addRow("Cycles (N):", self.spin_cycles)
        self.cb_forming = QCheckBox("Enable forming / pre-conditioning")
        fl.addRow("", self.cb_forming)
        self.le_form_v = QLineEdit()
        fl.addRow("Forming voltage (V):", self.le_form_v)
        self.le_form_width = QLineEdit()
        fl.addRow("Forming width:", self.le_form_width)
        self.spin_form_count = QSpinBox()
        self.spin_form_count.setRange(0, 100)
        self.spin_form_count.setValue(0)
        fl.addRow("Forming count:", self.spin_form_count)
        return w

    def _build_retention_form(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        self.ret_state = QComboBox()
        self.ret_state.addItems(["LRS", "HRS"])
        fl.addRow("State:", self.ret_state)
        self.le_ret_v_set = QLineEdit()
        fl.addRow("V_set (V):", self.le_ret_v_set)
        self.le_ret_v_reset = QLineEdit()
        fl.addRow("V_reset (V):", self.le_ret_v_reset)
        self.le_ret_set_w = QLineEdit()
        fl.addRow("Set width:", self.le_ret_set_w)
        self.le_ret_reset_w = QLineEdit()
        fl.addRow("Reset width:", self.le_ret_reset_w)
        self.le_holding = QLineEdit()
        fl.addRow("Holding times:", self.le_holding)
        btn_log = QPushButton("Fill log-scale preset")
        btn_log.clicked.connect(self._fill_log_holding)
        fl.addRow("", btn_log)
        self.le_ret_v_read = QLineEdit()
        fl.addRow("V_read (V):", self.le_ret_v_read)
        self.le_ret_read_w = QLineEdit()
        fl.addRow("Read width:", self.le_ret_read_w)
        return w

    def _build_read_retention_form(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        self.cb_rr_forming = QCheckBox("Enable forming / pre-conditioning")
        fl.addRow("", self.cb_rr_forming)
        self.le_rr_form_v = QLineEdit()
        fl.addRow("Forming voltage (V):", self.le_rr_form_v)
        self.le_rr_form_width = QLineEdit()
        fl.addRow("Forming width:", self.le_rr_form_width)
        self.spin_rr_form_count = QSpinBox()
        self.spin_rr_form_count.setRange(0, 100)
        self.spin_rr_form_count.setValue(0)
        fl.addRow("Forming count:", self.spin_rr_form_count)
        self.le_rr_holding = QLineEdit()
        fl.addRow("Holding times:", self.le_rr_holding)
        btn_log_rr = QPushButton("Fill log-scale preset")
        btn_log_rr.clicked.connect(self._fill_log_holding_rr)
        fl.addRow("", btn_log_rr)
        self.le_rr_v_read = QLineEdit()
        fl.addRow("V_read (V):", self.le_rr_v_read)
        self.le_rr_read_w = QLineEdit()
        fl.addRow("Read width:", self.le_rr_read_w)
        self.spin_rr_read_cycles = QSpinBox()
        self.spin_rr_read_cycles.setRange(1, 10000)
        self.spin_rr_read_cycles.setValue(1)
        fl.addRow("Read cycles (per holding time):", self.spin_rr_read_cycles)
        return w

    def _build_wgfm_form(self) -> QWidget:
        w = QWidget()
        fl = QFormLayout(w)
        self.wgfm_start_v = QLineEdit()
        fl.addRow("Start V (V):", self.wgfm_start_v)
        self.wgfm_stop_v = QLineEdit()
        fl.addRow("Stop V (V):", self.wgfm_stop_v)
        self.wgfm_step_v = QLineEdit()
        fl.addRow("Step V (V):", self.wgfm_step_v)
        self.wgfm_sweep_mode = QComboBox()
        self.wgfm_sweep_mode.addItems(["forward", "reverse", "double"])
        fl.addRow("Sweep mode:", self.wgfm_sweep_mode)
        self.wgfm_base_v = QLineEdit()
        fl.addRow("Base V (V):", self.wgfm_base_v)
        self.wgfm_off_time = QLineEdit()
        fl.addRow("Off time:", self.wgfm_off_time)
        self.wgfm_rise_time = QLineEdit()
        fl.addRow("Rise time:", self.wgfm_rise_time)
        self.wgfm_pulse_width = QLineEdit()
        fl.addRow("Pulse width:", self.wgfm_pulse_width)
        self.wgfm_fall_time = QLineEdit()
        fl.addRow("Fall time:", self.wgfm_fall_time)
        self.wgfm_measure_center = QLineEdit()
        self.wgfm_measure_center.setPlaceholderText("0.50")
        fl.addRow("Measure center ratio:", self.wgfm_measure_center)
        self.wgfm_interval_ratio = QLineEdit()
        self.wgfm_interval_ratio.setPlaceholderText("0.40")
        fl.addRow("Interval ratio:", self.wgfm_interval_ratio)
        self.wgfm_average_ratio = QLineEdit()
        self.wgfm_average_ratio.setPlaceholderText("0.30")
        fl.addRow("Average ratio:", self.wgfm_average_ratio)
        self.wgfm_dup_end = QCheckBox("Duplicate endpoint (double mode)")
        self.wgfm_dup_end.setChecked(True)
        fl.addRow("", self.wgfm_dup_end)
        return w

    def _fill_log_holding(self) -> None:
        self.le_holding.setText(", ".join(str(x) for x in DEFAULT_HOLDING_TIMES))

    def _fill_log_holding_rr(self) -> None:
        self.le_rr_holding.setText(", ".join(str(x) for x in DEFAULT_HOLDING_TIMES[:7]))

    def _on_terminal_changed(self, _index: int) -> None:
        is_3term = self.terminal_type.currentIndex() == 1
        self.seq_type.blockSignals(True)
        self.seq_type.clear()
        self.seq_type.addItems(self._seq_items_3term if is_3term else self._seq_items_2term)
        self.seq_type.setCurrentIndex(0)
        self.seq_type.blockSignals(False)
        self._sync_form_index()

    def _on_type_changed(self, _index: int) -> None:
        self._sync_form_index()

    def _form_index(self) -> int:
        """Current stacked form index: 0=LTP/LTD, 1=Retention, 2=Read retention, 3=TFT Gate Sweep."""
        if self.terminal_type.currentIndex() == 1:
            return 3
        return self.seq_type.currentIndex()

    def _sync_form_index(self) -> None:
        self.forms.setCurrentIndex(self._form_index())

    def _get_points(self):
        idx = self._form_index()
        try:
            if idx == 0:
                return self._get_ltp_ltd_points()
            if idx == 1:
                return self._get_retention_points()
            if idx == 2:
                return self._get_read_retention_points()
            return self._get_wgfm_points()
        except Exception as e:
            QMessageBox.warning(self, "Parameter error", str(e))
            return None

    def _get_ltp_ltd_points(self) -> List[Tuple[float, float, str]]:
        forming = None
        if self.cb_forming.isChecked():
            c = self.spin_form_count.value()
            if c < 1:
                raise ValueError("Forming count must be at least 1 when forming is enabled")
            forming = FormingConfig(
                voltage_v=_parse_float(self.le_form_v.text().strip(), "Forming voltage"),
                width_s=_parse_float(self.le_form_width.text().strip(), "Forming width"),
                count=c,
            )
        cycles = self.spin_cycles.value()
        if cycles < 1:
            raise ValueError("Cycles (N) must be at least 1")
        initial_hold = 0.0
        if self.le_initial_holding.text().strip():
            initial_hold = _parse_float(self.le_initial_holding.text().strip(), "Initial holding time")
        s = LTPLTDSettings(
            v_write_set_v=_parse_float(self.le_v_set.text().strip(), "V_write SET"),
            v_write_reset_v=_parse_float(self.le_v_reset.text().strip(), "V_write RESET"),
            width_s=_parse_float(self.le_width.text().strip(), "Write width"),
            interval_s=_parse_float(self.le_interval.text().strip(), "Interval"),
            v_read_v=_parse_float(self.le_v_read.text().strip(), "V_read"),
            read_width_s=_parse_float(self.le_read_width.text().strip(), "Read width"),
            cycles=cycles,
            forming=forming,
            initial_holding_time_s=initial_hold,
        )
        return generate_ltp_ltd(s)

    def _get_retention_points(self) -> List[Tuple[float, float, str]]:
        holding = _parse_holding_times(self.le_holding.text())
        if not holding:
            raise ValueError("Holding times cannot be empty")
        s = RetentionSettings(
            state=self.ret_state.currentText(),
            v_set_v=_parse_float(self.le_ret_v_set.text().strip(), "V_set"),
            v_reset_v=_parse_float(self.le_ret_v_reset.text().strip(), "V_reset"),
            set_width_s=_parse_float(self.le_ret_set_w.text().strip(), "Set width"),
            reset_width_s=_parse_float(self.le_ret_reset_w.text().strip(), "Reset width"),
            holding_times_s=holding,
            v_read_v=_parse_float(self.le_ret_v_read.text().strip(), "V_read"),
            read_width_s=_parse_float(self.le_ret_read_w.text().strip(), "Read width"),
        )
        return generate_retention(s)

    def _get_read_retention_points(self) -> List[Tuple[float, float, str]]:
        holding = _parse_holding_times(self.le_rr_holding.text())
        if not holding:
            raise ValueError("Holding times cannot be empty")
        forming = None
        if self.cb_rr_forming.isChecked():
            c = self.spin_rr_form_count.value()
            if c < 1:
                raise ValueError("Forming count must be at least 1 when forming is enabled")
            forming = FormingConfig(
                voltage_v=_parse_float(self.le_rr_form_v.text().strip(), "Forming voltage"),
                width_s=_parse_float(self.le_rr_form_width.text().strip(), "Forming width"),
                count=c,
            )
        s = ReadRetentionSettings(
            holding_times_s=holding,
            v_read_v=_parse_float(self.le_rr_v_read.text().strip(), "V_read"),
            read_width_s=_parse_float(self.le_rr_read_w.text().strip(), "Read width"),
            read_cycles=self.spin_rr_read_cycles.value(),
            forming=forming,
        )
        return generate_read_retention(s)

    def _get_wgfm_points(self):
        def f(name, default=None):
            le = getattr(self, f"wgfm_{name}", None)
            if le is None or not hasattr(le, "text"):
                return default
            t = le.text().strip()
            return t or default
        mc = f("measure_center", "0.50")
        ir = f("interval_ratio", "0.40")
        ar = f("average_ratio", "0.30")
        params = WGFMUGateSweepPIVParams(
            start_v=_parse_float(self.wgfm_start_v.text().strip(), "Start V"),
            stop_v=_parse_float(self.wgfm_stop_v.text().strip(), "Stop V"),
            step_v=_parse_float(self.wgfm_step_v.text().strip(), "Step V"),
            sweep_mode=self.wgfm_sweep_mode.currentText(),
            base_v=_parse_float(self.wgfm_base_v.text().strip() or "0", "Base V"),
            off_time=f("off_time") or "0",
            rise_time=f("rise_time") or "0",
            pulse_width=_parse_float(self.wgfm_pulse_width.text().strip(), "Pulse width"),
            fall_time=f("fall_time") or "0",
            measure_center_ratio=float(mc) if mc else 0.50,
            interval_ratio=float(ir) if ir else 0.40,
            average_ratio=float(ar) if ar else 0.30,
            duplicate_endpoint=self.wgfm_dup_end.isChecked(),
        )
        return generate_points("wgfm_gate_sweep_piv", wgfm_gate_sweep_piv=params)

    def _update_preview(self) -> None:
        points = self._get_points()
        if points is not None:
            self.plot_widget.plot_points(
                points,
                downsample=self.downsample_cb.isChecked(),
            )

    def _base_filename(self) -> str:
        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        idx = self._form_index()
        type_names = ["ltp_ltd", "retention", "read_retention", "wgfm_gate_sweep_piv"]
        type_name = type_names[idx] if idx < len(type_names) else "sequence"
        if idx == 0:
            key = f"cycles{self.spin_cycles.value()}"
        elif idx == 1:
            key = self.ret_state.currentText()
        elif idx == 2:
            key = "read_ret"
        else:
            key = self.wgfm_sweep_mode.currentText() if idx == 3 else "wgfm"
        return f"{type_name}_{date}_{key}"

    def _export_csv(self) -> None:
        points = self._get_points()
        if points is None:
            return
        default_name = self._base_filename() + ".csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", default_name, "CSV (*.csv)"
        )
        if path:
            try:
                export_csv(points, path)
                QMessageBox.information(self, "Export", f"Saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export error", str(e))

    def _export_xlsx(self) -> None:
        points = self._get_points()
        if points is None:
            return
        default_name = self._base_filename() + ".xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Excel", default_name, "Excel (*.xlsx)"
        )
        if path:
            try:
                idx = self._form_index()
                sheet = ["ltp_ltd", "retention", "read_retention", "wgfm_gate_sweep_piv"][idx]
                export_xlsx(points, path, sheet_name=sheet)
                QMessageBox.information(self, "Export", f"Saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export error", str(e))

    def _show_table(self) -> None:
        """펄스 테이블을 대화상자로 표시해 복사·붙여넣기 할 수 있게 함."""
        points = self._get_points()
        if points is None:
            return
        dlg = TableViewDialog(points, self)
        dlg.exec()


def run_gui() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
