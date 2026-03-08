# Pulse Sequence Generator

A pulse sequence generation tool for RRAM/Memristor and TFT measurements.

## Features

- GUI (PySide6) for parameter input, waveform preview, and export
- CLI (YAML-based) for automated sequence generation
- 2-terminal sequence support:
  - LTP/LTD
  - Retention (HRS/LRS)
  - Read Retention
- 3-terminal sequence support:
  - TFT Gate Sweep (forward/reverse/double)
- Time unit parsing (`s`, `ms`, `us`, `ns`)
- Export to CSV and Excel (`.xlsx`)
- Default output columns: `time_s`, `voltage_v`, `segment_label`
- Additional TFT columns for measurement windows, index, and sweep direction
- Segment labels (e.g., `SET_WRITE`, `READ`, `HOLD`, `OFF`, `PULSE`)


