# 보 모델 분석 및 주근 배근 정보 변경 시스템

IFC(IFC2X3, Tekla Structures 출력) 보 모델에서 <b>주근(상부근·하부근)을 자동으로 찾아 직경·개수를 변경하고, 피복두께·늑근 직경·늑근 굽힘반경을 고려해 등간격으로 재배치</b>하는 Python 도구입니다. 3D 형상과 IFC 메타데이터(직경, 단면적, 수량, 중량, 간격)를 함께 갱신합니다.

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 상부근 | 4-D22, 중심간격 79.87 mm | **5-D19, 중심간격 59.90 mm** |
| 하부근 | 4-D22, 중심간격 79.87 mm | **5-D19, 중심간격 59.90 mm** |
| 순간격 | 57.67 mm | 40.80 mm (최소 33.3 mm 이상 → OK) |
| 주근 중심 높이 (Z) | 상 5936.20 / 하 5263.80 | 상 5937.75 / 하 5262.25 |
| 철근 중량 (상/하) | 74.7 / 65.9 kg | 69.1 / 61.0 kg |
| Assembly 철근 총중량 | 175.3 kg | 164.8 kg |


---

## 1. 실행 방법

### 1.1 프로그램 실행 (권장)

| | 켜기 (켜져 있으면 재시작) | 끄기 |
|---|---|---|
| **Windows** | 폴더에서 `START_Windows.bat` 더블클릭 | `STOP_Windows.bat` |
| **macOS** | 터미널에 `bash ` 입력 → `START_Mac.command`를 터미널 창으로 끌어다 놓고 Enter | `STOP_Mac.command` |

실행하면 잠시 뒤 브라우저에 프로그램 화면이 열립니다.

**Python이 없어도 됩니다.** START 파일이 컴퓨터 상태를 확인해서 필요한 것만 이 폴더 안에 준비합니다. 시스템에는 아무것도 설치하지 않으므로 폴더를 지우면 깨끗이 제거됩니다.

| 컴퓨터 상태 | START 실행 시 동작 |
|---|---|
| Python 3.10+와 라이브러리가 이미 있음 | 설치 없이 바로 실행 |
| Python만 있음 | 라이브러리만 폴더 안(`.venv`)에 설치 (1~3분, 최초 1회) |
| Python 없음 | 전용 Python 3.12와 라이브러리를 폴더 안(`.uv`, `.venv`)에 설치 (2~5분, 최초 1회, 인터넷 필요) |

**참고**
- **Windows:** 파란 "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**을 누르세요.
- **macOS:** `START_Mac.command`를 Finder에서 더블클릭해도 되지만, 인터넷에서 받은 서명 없는 파일이라 Apple 보안 경고가 뜰 수 있습니다. 위 표의 터미널 방법은 경고 없이 실행됩니다. 더블클릭으로 경고가 떴다면 "완료"를 누르고 <b>시스템 설정 → 개인정보 보호 및 보안 → "그래도 열기"</b>를 누르세요.
- VS Code 같은 편집기 안에서 클릭하면 실행되지 않고 내용만 열립니다.

**사용 순서**
1. 왼쪽 ①에서 원본 IFC 파일을 선택합니다.
2. 왼쪽 ②에서 변경할 값(직경·개수·간격)을 입력합니다. 과제 조건인 D19, 5개, 자동 등간격이 기본값입니다.
3. 왼쪽 ③에서 결과를 저장할 폴더와 파일 이름을 정합니다.
4. 본문 위쪽의 **▶ 변경 실행**을 누릅니다.

**버튼·입력 설명**

| 위치 | 버튼 / 입력 | 설명 |
|---|---|---|
| 왼쪽 맨 위 | 🔄 초기화 (처음 상태로) | 입력값과 결과를 모두 지우고 처음 상태로 되돌립니다. 프로그램 자체를 재시작하려면 START 파일을 다시 실행합니다. |
| ① 입력 IFC 파일 | 파일 경로 | 변경할 원본 IFC 파일 경로입니다. 직접 입력해도 됩니다. |
| | 📂 컴퓨터에서 IFC 파일 찾기 | Finder·탐색기 창을 열어 IFC 파일을 고릅니다. 고른 경로가 위 칸에 들어갑니다. |
| ② 변경할 값 입력 | 주근 직경 (KS D 3504) | D10~D32 중에서 고릅니다. 공칭지름이 함께 표시됩니다. |
| | 주근 개수 (상·하부 각각) | 2~12개. 숫자를 입력하거나 −/+ 버튼으로 바꿉니다. |
| | 주근 간격 | **자동**: 유효폭을 등분한 간격으로 배치합니다. **직접 입력**: 중심간격을 mm로 지정합니다. |
| | 중심간격 (mm) | "직접 입력"을 고르면 나타납니다. 보 중심 기준 좌우 대칭으로 배치하며, 바로 아래 👉 줄에 입력 가능한 범위가 표시됩니다. |
| | 적용 대상 | 상·하부 / 상부근만 / 하부근만. 과제는 상·하부입니다. |
| | 설계 기준값 (펼치기) | 피복두께(기본 40mm)와 굵은골재 최대치수(기본 25mm, 최소 순간격 계산용)를 바꿉니다. |
| ③ 결과 저장 위치 | 저장 폴더 | 결과 IFC를 저장할 폴더입니다. 기본값은 프로그램 폴더의 `output`입니다. |
| | 📁 저장할 폴더 선택 | Finder·탐색기 창을 열어 저장 폴더를 고릅니다. |
| | 파일 이름 | `원본이름_D19x5.ifc`처럼 자동으로 제안되며, 직접 고칠 수 있습니다. 아래 "저장 경로"에 실제 저장될 전체 경로가 표시됩니다. |
| 본문 위쪽 | ▶ 변경 실행 | 진행 막대와 함께 변경 → 저장 → 검증을 차례로 수행합니다. 기준 미달(NG)이거나 저장 경로가 원본과 같으면 눌리지 않습니다. |
| | 📂 저장 폴더 열기 | 변경이 끝나면 나타납니다. 결과 IFC가 저장된 폴더를 엽니다. |
| 본문 탭 | ① 모델 분석 | 원본 보·늑근·주근 정보 표, 배치 규칙 재현 검증, 현재 단면과 3D 모델을 보여 줍니다. |
| | ② 변경 미리보기 | 입력값을 바꾸는 즉시 변경 전후 단면과 간격·순간격·배근폭·판정(OK/NG)·단면적·중량을 보여 줍니다. |
| | ③ 결과 | 저장된 IFC를 다시 읽어 속성 변경 내역, 3D 모델, 단면을 보여 줍니다. "검증 상세 로그"와 "처리 로그"는 눌러서 펼칩니다. |

**안전장치**
- 순간격 부족이나 늑근·피복 침범(NG)이면 실행 버튼이 비활성화되고 사유가 표시됩니다.
- 저장 경로가 원본 파일과 같으면 실행되지 않습니다(원본 보호).
- 결과 파일이 Tekla나 뷰어에서 열려 있어 저장할 수 없으면 안내 메시지를 띄웁니다.

### 1.2 명령어로 실행 (터미널 / PowerShell)

화면 없이 명령어로 변환합니다. 원본 IFC 파일을 미리 `input` 폴더에 넣어 두고, 아래 명령을 **한 칸씩 복사해 붙여넣으세요.**
예시의 원본 파일 이름은 `girder rebar.ifc`입니다. 파일 이름에 띄어쓰기가 있으면 따옴표로 감싸야 합니다.

**macOS (터미널)**

1. 프로그램 폴더로 이동합니다. 경로는 실제 위치로 바꾸세요.
```bash
cd ~/Downloads/girder_rebar_modifier
```
2. 최초 1회만: Python 환경을 준비합니다. **Python 3.10 이상이 있으면 그것을 쓰고, 없으면 이 폴더 안에 Python 3.12를 자동 설치**합니다(인터넷 필요). 아래 세 줄을 그대로 붙여넣으세요.
```bash
PY=""; for c in python3.13 python3.12 python3.11 python3.10 python3; do if command -v $c >/dev/null 2>&1 && $c -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then PY=$c; break; fi; done
if [ -n "$PY" ]; then $PY -m venv .venv; else curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$PWD/.uv" UV_NO_MODIFY_PATH=1 sh && UV_PYTHON_INSTALL_DIR="$PWD/.uv/python" "$(ls .uv/uv .uv/bin/uv 2>/dev/null | head -1)" venv .venv --python 3.12 --seed; fi
.venv/bin/python -m pip install -r requirements.txt
```
3. 변환합니다 (D19 × 5개, 자동 등간격). `output` 폴더에 결과 IFC가 생깁니다.
```bash
.venv/bin/python src/modify_rebar.py "input/girder rebar.ifc" "output/girder rebar_D19x5.ifc" --size 19 --count 5
```
4. (선택) 결과를 검증합니다.
```bash
.venv/bin/python src/verify_rebar.py "input/girder rebar.ifc" "output/girder rebar_D19x5.ifc"
```

**Windows (PowerShell)**

1. 프로그램 폴더로 이동합니다. 따옴표 안의 경로를 실제 위치로 바꾸세요.
```powershell
cd "C:\Users\사용자이름\Downloads\girder_rebar_modifier"
```
2. 최초 1회만: Python 환경을 준비합니다. **Python 3.10 이상이 있으면 그것을 쓰고, 없으면 이 폴더 안에 Python 3.12를 자동 설치**합니다(인터넷 필요). 아래 세 줄을 그대로 붙여넣으세요.
```powershell
$py = $null; foreach ($c in "python", "py") { try { if ((& $c -c "import sys; print(sys.version_info >= (3, 10))" 2>$null) -eq "True") { $py = $c; break } } catch {} }
if ($py) { & $py -m venv .venv } else { $env:UV_INSTALL_DIR = "$PWD\.uv"; $env:UV_NO_MODIFY_PATH = "1"; $env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv\python"; powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"; $uv = Get-ChildItem "$PWD\.uv" -Recurse -Filter uv.exe | Select-Object -First 1; & $uv.FullName venv .venv --python 3.12 --seed }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
3. 변환합니다 (D19 × 5개, 자동 등간격). `output` 폴더에 결과 IFC가 생깁니다.
```powershell
.\.venv\Scripts\python.exe src\modify_rebar.py "input\girder rebar.ifc" "output\girder rebar_D19x5.ifc" --size 19 --count 5
```
4. (선택) 결과를 검증합니다.
```powershell
.\.venv\Scripts\python.exe src\verify_rebar.py "input\girder rebar.ifc" "output\girder rebar_D19x5.ifc"
```

성공하면 마지막에 `[저장] output...` 줄이 나오고, `output` 폴더에 결과 IFC가 생깁니다.

**옵션 (`modify_rebar.py`)**

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--size` | 19 | 주근 호칭 (KS D 3504: 10, 13, 16, 19, 22, 25, 29, 32) |
| `--count` | 5 | 상·하부 각 주근 개수 |
| `--cover` | 40 | 피복두께 mm (구조일반사항) |
| `--position` | BOTH | `TOP` / `BOTTOM` / `BOTH` |
| `--spacing` | (자동) | 주근 중심간격 mm 직접 지정. 보 중심 기준 대칭 배치 |
| `--max-aggregate` | 25 | 굵은골재 최대치수 mm (최소 순간격 검토용) |
| `--report` | – | 변경 전후 내역 JSON 저장 경로 |

다른 조합도 바로 쓸 수 있습니다. 예: `--size 25 --count 3`. 순간격이 부족하면(예: `--size 25 --count 6`) 경고를 출력합니다.

## 2. 폴더 구성

```
├─ START_Mac.command / STOP_Mac.command     # ★ macOS 실행(켜져 있으면 재시작) / 종료
├─ START_Windows.bat / STOP_Windows.bat     # ★ Windows 실행 / 종료
├─ launcher.py            # 실행기: 시작/재시작/종료, 브라우저 열기 (전용 Python 설치는 START 파일이 담당)
├─ src/
│  ├─ app.py              # 프로그램 화면 (Streamlit) - 아래 두 모듈을 그대로 호출
│  ├─ modify_rebar.py     # 분석 → 배근 계산 → IFC 갱신 (핵심 로직, CLI 겸용)
│  └─ verify_rebar.py     # 결과 IFC 독립 검증 + 단면 비교 이미지
├─ input/                 # 원본 IFC를 넣는 폴더 (비어 있음)
├─ output/                # 결과 IFC가 저장되는 기본 폴더 (비어 있음)
├─ docs/
│  ├─ section_before_after.png          # 단면 비교 캡처
│  ├─ ui_2_preview.png, ui_3_progress.png, ui_4_result.png   # 화면 캡처
│  └─ AI_활용_및_접근방식.md
├─ requirements.txt
```

---

## 3. 도메인 분석

### 3.1 원본 모델 구조 (IFC2X3, 단위 mm)

```
IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey
                                         └ IfcElementAssembly "GIRDER" (G0, 현장타설)
                                             ├ IfcBeam            400×800, L=3000, C30
                                             ├ IfcReinforcingBar  하부근 D22×4, L=5420 (3000 + 정착 1210×2)
                                             ├ IfcReinforcingBar  상부근 D22×4, L=6140 (3000 + 정착 1570×2)
                                             └ IfcReinforcingBar  늑근 D13×16, @193 (Shape 54, 90° 갈고리)
```

- 철근 1세트 = `IfcReinforcingBar` 1개. 형상은 `IfcSweptDiskSolid`(반경 = 공칭지름/2) 1개를 `IfcMappedItem` n개로 복제하며, 각 MappedItem의 오프셋이 철근 1개의 위치입니다.
- 로컬 X축 = 철근 길이 방향, 로컬 Y축 = 배근(분배) 방향.
- 주근과 늑근은 형상으로 구분합니다. 주근은 `IfcLine` 기반 직선이고, 늑근은 `IfcCompositeCurve`(직선 + `IfcCircle` 굽힘)입니다.
- 길이 5420/6140은 참고자료의 인장정착길이(하부 1210, 상부 1570)와 정확히 일치합니다.

### 3.2 주근 배치 규칙 (원본에서 역산 → 재현 검증)

늑근(D13, Ø12.7)의 굽힘 중심선 반경은 33.85 mm이므로 <b>굽힘 내반경은 33.85 − 6.35 = 27.5 mm</b>입니다. 모서리 주근은 늑근 평탄부 위에 놓인 채 굽힘부 안쪽에 밀착됩니다. 굽힘 내반경(27.5)이 주근 반경(11.1 또는 9.55)보다 크므로, 주근 중심은 굽힘 중심과 같은 수직선에 놓입니다.

```
폭 방향 끝 주근 중심 = 보 측면 + 피복(40) + 늑근 직경(12.7) + 굽힘 내반경(27.5) = 측면 + 80.2
높이 방향 주근 중심 = 보 상·하면 ∓ (피복 40 + 늑근 12.7 + 주근 반경)
중간 주근          = 양 끝 사이 (n−1) 등분
```

원본 D22×4에 이 식을 적용하면 Tekla 좌표가 <b>오차 0.000 mm로 재현</b>됩니다.
(X = 5880.2 / 5960.07 / 6039.93 / 6119.8, Z = 5263.8 / 5936.2. 스크립트가 매 실행마다 먼저 이 재현 검증을 수행합니다.)

### 3.3 D19×5 적용 결과

- 유효 배근 폭 = 400 − 2×80.2 = **239.6 mm** → 중심간격 239.6 / 4 = **59.9 mm**
- 순간격 = 59.9 − 19.1 = **40.8 mm** ≥ max(25, 1.0·d<sub>b</sub>=19.1, 4/3×25=33.3) = 33.3 mm → **1단 배근 가능** (KDS 14 20 50)
- Z: 하부 5200 + 40 + 12.7 + 9.55 = **5262.25**, 상부 6000 − 62.25 = **5937.75**
- 늑근과는 접촉(간섭 0) 상태로, 원본 Tekla 배근과 같은 방식입니다.

## 4. IFC 갱신 내용

| 구분 | 갱신 항목 |
|---|---|
| 형상 | `IfcSweptDiskSolid` 반경 11.1 → 9.55, MappedItem 4 → 5개, 오프셋 0/59.9/…/239.6. RepresentationMap 1개를 공유해 중복을 없앴고, 프레젠테이션 레이어와 스타일(색상)은 유지 |
| 배치 | `IfcLocalPlacement` 원점 Z 재계산 (첫 철근 기준) |
| IFC 속성 | `NominalDiameter` 19.1, `CrossSectionArea` 286.5 mm², `BarLength`, `BarRole` = MAIN |
| Tekla Pset | Size 19, Number of bars in group 5, Weight / Weight total in group, Spacing exact `4*60`, Spacing target 59.9 |
| Assembly | Cast unit rebar weight 175.3 → 164.8 kg (주근 중량 증감 반영) |
| 정리 | 구 형상 엔티티 제거 (다른 객체가 참조하지 않는 것만) |

**구현상 주의점:** Tekla는 같은 `IfcPropertySingleValue` 인스턴스(예: `Size`, `Number of bars in group`, `Spacing exact`)를 여러 철근의 Pset이 공유합니다. 값을 직접 바꾸면 다른 철근까지 바뀌므로, 새 속성 객체를 만들어 해당 Pset에서만 교체합니다. GlobalId는 유지되므로 원본 객체 추적이 가능합니다.

## 5. 검증 (`verify_rebar.py`)

계산 로직을 재사용하지 않고, 결과 IFC의 <b>실제 3D 메시</b>를 다시 생성해 측정합니다.

1. 스키마 유효성. 결과 파일은 오류 5건 → 3건으로 줄었습니다. 남은 3건은 원본 Tekla 출력에 있던 것(Pset_BeamCommon의 빈 IfcBoolean 2건, 늑근 CrossSectionArea 누락)으로, 주근 범위 밖이라 손대지 않았습니다.
2. 형상과 메타데이터 일치: 메시 직경, 메시 개수 ↔ NominalDiameter, Size, Number of bars
3. 피복: 주근 표면 ~ 보 표면 ≥ 40 + 12.7
4. 등간격 및 최소 순간격
5. 늑근 간섭 여부

결과는 화면 ③ 결과 탭의 "검증 상세 로그"(CLI는 터미널 출력)에서 확인합니다. 제공된 모델 기준으로 변경 전후 모두 <b>PASS</b>입니다.

## 6. 가정 및 한계

- 정착길이(상부 1570 / 하부 1210)는 참고자료의 구조일반사항 값을 그대로 유지했습니다. 실제 설계에서는 인장정착길이가 철근 직경에 비례하므로(l<sub>d</sub> ∝ d<sub>b</sub>), D19로 바꾸면 정착길이를 줄일 여지가 있습니다. 필요하면 길이 재계산 옵션으로 확장할 수 있습니다.
- 주근 단면적 비교: 4-D22 = 1548 mm², 5-D19 = 1433 mm²(약 −7.5%)입니다. 구조 검토(휨 내력)는 과제 범위 밖이라 수행하지 않았습니다.
- 늑근(D13@193)은 변경 대상이 아니므로 그대로 둡니다.
- 1개 보 / 직선 주근 세트를 대상으로 하며, 여러 보가 있는 모델은 보별 반복으로 확장할 수 있도록 함수 단위로 분리했습니다.
