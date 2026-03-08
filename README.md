# RRAM / Memristor Pulse Sequence Generator

엑셀 LTP/LTD pulse 설정툴과 동일한 기능을 코드로 구현한 데스크톱/CLI 도구입니다.
Time–Voltage 테이블을 생성해 CSV/Excel로 저장합니다.

## 설치

```bash
pip install -r requirements.txt
```

## 배포 / 다른 PC에 설치

### 방법 1: 실행 파일(.exe) 만들기 (Python 없이 실행)

Windows에서 **PyInstaller**로 GUI를 단일 실행 파일로 묶을 수 있습니다. 다른 PC에는 Python을 설치하지 않아도 됩니다.

1. **빌드용 패키지 설치**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-build.txt
   ```

2. **실행 파일 빌드**
   ```bash
   pyinstaller pulse_sequence.spec
   ```

3. **결과**
   - `dist/PulseSequenceGenerator.exe` 가 생성됩니다.
   - 이 **.exe 파일 하나**를 다른 PC로 복사해 두 번 클릭하면 실행됩니다.
   - (필요하면 `dist` 폴더 전체를 복사해도 됩니다.)

### 방법 2: 폴더 형태로 배포 (실행이 더 빠름)

한 파일이 아니라 폴더로 빌드하려면 아래처럼 합니다.

```bash
pyinstaller --name PulseSequenceGenerator --windowed --onedir main.py
```

- `dist/PulseSequenceGenerator/` 폴더 안에 `PulseSequenceGenerator.exe`와 DLL 등이 생성됩니다.
- 이 **폴더 전체**를 다른 PC로 복사한 뒤, 폴더 안의 `PulseSequenceGenerator.exe`를 실행합니다.

### 방법 3: 설치 프로그램(인스톨러) 만들기

실행 파일을 만들었다면, **Inno Setup**(Windows)으로 설치 마법사(.exe 인스톨러)를 만들 수 있습니다.

1. [Inno Setup](https://jrsoftware.org/isinfo.php) 설치
2. 스크립트에서 “실행 파일”을 `dist/PulseSequenceGenerator.exe`(또는 `dist/PulseSequenceGenerator/PulseSequenceGenerator.exe`)로 지정
3. 빌드하면 `Setup_PulseSequenceGenerator.exe` 같은 설치 파일이 생성됩니다.
4. 다른 PC에서 이 설치 파일을 실행하면 바탕화면/시작 메뉴에 바로가기가 생깁니다.

### 요약

| 목적 | 추천 |
|------|------|
| “exe 하나만 넘기고 끝” | `pyinstaller pulse_sequence.spec` → `dist/PulseSequenceGenerator.exe` 복사 |
| 실행 속도·호환성 중시 | `--onedir` 로 빌드 후 `dist/PulseSequenceGenerator` 폴더 통째로 복사 |
| 바탕화면/시작 메뉴 설치 | PyInstaller로 exe 만든 뒤 Inno Setup으로 인스톨러 제작 |

## 사용법

### GUI (데스크톱)

```bash
python main.py
```

- **Terminal** 선택: **2 terminal** (LTP/LTD, Read retention, Retention (HRS/LRS)) / **3 terminal** (TFT Gate Sweep)
- 파라미터 입력 후 **Update preview**로 파형 확인
- **Export CSV** / **Export Excel (xlsx)** 로 저장
- 파일명 자동 제안: `{sequence_type}_{date}_{key_params}.csv`

### CLI (YAML 설정)

```bash
python -m cli config_template.yaml -o output.csv
python -m cli config_template.yaml -o output.csv --xlsx --preview
```

- `-o, --output`: 출력 CSV 경로 (생략 시 자동 생성)
- `--xlsx`: 동일 이름으로 `.xlsx` 추가 저장
- `--preview`: matplotlib으로 파형 미리보기

#### 시간 단위 (GUI·YAML 공통)

- **아무것도 안 붙이면** → 초(s)
- **s** → 초, **m** 또는 **ms** → 밀리초, **u** 또는 **us** → 마이크로초, **n** 또는 **ns** → 나노초
  예: `100`, `100u`, `1m`, `50n`

## 시퀀스 타입

- **2 terminal**: RRAM/멤리스터 2단자 (LTP/LTD, Retention, Read retention)
- **3 terminal**: TFT 등 게이트 스위핑 (TFT Gate Sweep)

| 타입                          | 설명                                                                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **LTP/LTD** (2 terminal)             | (write) + interval + (read) + interval 을 1 cycle로, LTP(SET) N회 → LTD(RESET) N회. 각 write 뒤 read 포함. forming 옵션 가능. |
| **Retention (HRS/LRS)** (2 terminal) | set 또는 reset 후 holding time 대기 → read. holding time은 로그 스케일 리스트 선택 가능.                                      |
| **Read retention** (2 terminal)      | (선택) forming 후 write 없이 (hold → read) 반복. forming 옵션 제공.                                                           |
| **TFT Gate Sweep** (3 terminal)      | Gate voltage sweep (forward/reverse/double) + PIV on-time 측정. OFF→RISE→PULSE→FALL 4구간.                                   |

## 출력 형식

- **CSV / xlsx** 공통 컬럼: `time_s`, `voltage_v`, `segment_label`
- TFT Gate Sweep(3 terminal) 시퀀스는 추가 컬럼: `measure_center_s`, `interval_s`, `average_s`, `point_index`, `sweep_direction` (및 `measure_start_s`, `measure_end_s`)
- segment_label 예: `SET_WRITE`, `RESET_WRITE`, `READ`, `HOLD`, `IDLE`, `FORMING` / TFT Gate Sweep: `OFF`, `RISE`, `PULSE`, `FALL`
- 파형은 step waveform: 각 구간이 (t_start, V), (t_end, V)로 정의되며, V=0 구간도 명시

## 테스트

```bash
python -m pytest tests/ -v
```

## 프로젝트 구조

```
core/
  sequence.py         # LTP/LTD, retention, read_retention 파라미터 및 생성
  sequence_registry.py # 시퀀스 타입별 generate_points 디스패치
  sequences/
    wgfm_gate_sweep_piv.py  # WGFMU gate sweep + PIV 시퀀스
  models.py           # WGFMU용 Pydantic 모델 (WGFMUGateSweepPIVParams)
  export.py           # CSV / xlsx 저장 (확장 컬럼 지원)
  units.py            # "100us", "1ms" 등 → 초 변환
  schema.py           # CLI용 Pydantic 스키마
ui/
  app.py        # PySide6 GUI
cli.py          # Typer CLI (YAML → CSV/xlsx)
main.py         # GUI 실행 진입점
config_template.yaml  # YAML 설정 예시
tests/          # pytest
```

## 예시 (LTP/LTD)

- V_write_set = -2.3 V, width = 100 µs, interval = 100 µs
- V_read = 0.2 V, read_width = 50 µs
- cycles = 100
- LTD: V_write_reset = +1.2 V, 동일 width/interval/read

Retention holding times 예: `[1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1, 3, 10]` (초)

### TFT Gate Sweep (3 terminal) 예시

**예시 1) double sweep**

- StartV = -5 V, StopV = 5 V, StepV = 0.1 V  
- BaseV = 0 V  
- off = 1 s, rise/fall = 100 ns, pulse width = 100 µs  

```yaml
sequence_type: wgfm_gate_sweep_piv
wgfm_gate_sweep_piv:
  start_v: -5
  stop_v: 5
  step_v: 0.1
  sweep_mode: double
  base_v: 0
  off_time: 1
  rise_time: "100n"
  pulse_width: "100u"
  fall_time: "100n"
```

**예시 2) reverse sweep**

- StartV = -5 V, StopV = 5 V, StepV = 0.2 V  
- reverse, pulse width = 1 ms  

```yaml
sequence_type: wgfm_gate_sweep_piv
wgfm_gate_sweep_piv:
  start_v: -5
  stop_v: 5
  step_v: 0.2
  sweep_mode: reverse
  base_v: 0
  off_time: 0
  rise_time: "100n"
  pulse_width: "1m"
  fall_time: "100n"
```
