# 보 모델 분석 및 주근 배근 정보 변경 시스템

> ## ▶ 빠른 실행 (Python이 없어도 됨)
>
> **Windows** — 압축을 푼 폴더에서 `START_Windows.bat` 더블클릭
> (파란 "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**)
>
> **macOS** — 아래 방법이 **보안 경고 없이** 실행됩니다.
> 1. **터미널** 앱을 엽니다 (Spotlight에서 `터미널` 검색)
> 2. `bash ` (bash 다음 한 칸 띄우기)를 입력하고, Finder에서 **`START_Mac.command` 파일을 터미널 창으로 끌어다 놓은 뒤** Enter
>    ```
>    bash /Users/사용자/Downloads/girder_rebar_modifier/START_Mac.command
>    ```
> 3. 끝나면 브라우저에 프로그램 화면이 열립니다. 필요한 것만 자동으로 준비합니다(아래 표).
>
> | 컴퓨터 상태 | START 실행 시 동작 |
> |---|---|
> | Python 3.10+와 라이브러리가 이미 있음 | **설치 없이 바로 실행** |
> | Python만 있음 | Python 다운로드 없이 **라이브러리만** 폴더 안(`.venv`)에 설치 (1~3분, 최초 1회) |
> | Python 없음 | 전용 Python 3.12와 라이브러리를 폴더 안(`.uv`, `.venv`)에 설치 (2~5분, 최초 1회) |
>
> 어떤 경우에도 시스템에는 설치하지 않습니다. 폴더를 지우면 깨끗이 제거됩니다.
>
> ※ macOS에서 `START_Mac.command`를 **더블클릭**하면, 인터넷에서 받은 서명되지 않은 파일이라 Apple 보안 경고가 뜹니다.
> 그때는 "완료"를 누르고 위의 터미널 방법을 쓰거나, **시스템 설정 → 개인정보 보호 및 보안 → "그래도 열기"**를 누르세요.

IFC(IFC2X3, Tekla Structures 출력) 보 모델에서 **주근(상부근·하부근)을 자동으로 찾아 직경·개수를 변경하고, 피복두께·늑근 직경·늑근 굽힘반경을 고려해 등간격으로 재배치**하는 Python 도구입니다. 3D 형상과 IFC 메타데이터(직경, 단면적, 수량, 중량, 간격)를 함께 갱신합니다.

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 상부근 | 4-D22, 중심간격 79.87 mm | **5-D19, 중심간격 59.90 mm** |
| 하부근 | 4-D22, 중심간격 79.87 mm | **5-D19, 중심간격 59.90 mm** |
| 순간격 | 57.67 mm | 40.80 mm (최소 33.3 mm 이상 → OK) |
| 주근 중심 높이 (Z) | 상 5936.20 / 하 5263.80 | 상 5937.75 / 하 5262.25 |
| 철근 중량 (상/하) | 74.7 / 65.9 kg | 69.1 / 61.0 kg |
| Assembly 철근 총중량 | 175.3 kg | 164.8 kg |

![단면 비교](docs/section_before_after.png)

---

## 1. 실행 환경

- **별도 설치 불필요.** START 파일이 기존 Python을 먼저 찾아 쓰고, 없을 때만 전용 Python 3.12를 자동 설치합니다. 직접 실행하려면 Python 3.10 이상이 필요합니다(3.12·3.13에서 테스트)
- 라이브러리: `ifcopenshell` 0.8 이상(0.9.0에서 테스트), `numpy`, `matplotlib`(검증 이미지), `streamlit`·`plotly`·`pandas`(웹 화면)

```bash
pip install -r requirements.txt      # 명령줄(CLI)로 직접 실행할 때만 필요. START 파일은 자동 처리
```

## 2. 실행 방법

### 2.1 프로그램 화면 (권장)

| OS | 켜기 / 재시작 | 끄기 |
|---|---|---|
| **macOS** | Finder에서 **`START_Mac.command` 더블클릭** | `STOP_Mac.command` |
| **Windows** | 파일 탐색기에서 **`START_Windows.bat` 더블클릭** | `STOP_Windows.bat` |

- **컴퓨터에 Python이 없어도 됩니다.** 이미 설치된 Python과 라이브러리가 있으면 그대로 쓰고, 없는 것만 이 폴더 안에 자동 설치합니다. 위의 '빠른 실행' 표를 참고하세요.
- **켜져 있는 상태에서 START를 다시 누르면 재시작**합니다.
- macOS에서 **"열지 않음 / 악성 코드가 없음을 확인할 수 없습니다"** 경고가 뜨면, 인터넷에서 받은 파일이라 Mac이 막은 것입니다. **"완료"**를 누른 뒤 아래 중 하나를 하세요.
  1. **시스템 설정 → 개인정보 보호 및 보안** 아래쪽 *"START_Mac.command이(가) 차단되었습니다"* 옆의 **"그래도 열기"** 클릭 → 다시 더블클릭
  2. 또는 터미널에서 한 번만 실행: `xattr -dr com.apple.quarantine ~/Downloads/girder_rebar_modifier` (폴더 경로는 실제 위치로)
- VS Code 같은 편집기 안에서 클릭하면 실행되지 않고 내용만 열립니다. 반드시 Finder나 탐색기에서 더블클릭하세요.
- 화면의 **🔄 초기화** 버튼은 입력값과 결과를 처음 상태로 되돌립니다.

**사용 순서 (왼쪽 패널)**

| 단계 | 내용 |
|---|---|
| ① 입력 IFC 파일 | **[📂 컴퓨터에서 IFC 파일 찾기]**로 Finder·탐색기 선택 창을 열어 원본 IFC를 고름 (경로 직접 입력도 가능) |
| ② 변경할 값 입력 | **주근 직경**(D10~D32), **주근 개수**, **주근 간격**(자동 등간격 / 직접 입력 mm), 적용 대상(상·하부/상부/하부) |
| ③ 결과 저장 위치 | **[📁 저장할 폴더 선택]**으로 폴더를 고르고 파일 이름 입력. 이름은 `원본_D19x5.ifc`처럼 자동 제안됨 |
| ▶ 변경 실행 | 진행 막대와 함께 "변경 중" 단계가 표시됨 → 지정 경로에 IFC 저장 → 자동 검증 → **[📂 저장 폴더 열기]** |

**화면 탭**

| 탭 | 기능 |
|---|---|
| ① 모델 분석 | 보·늑근·주근 정보 표, 배치 규칙 재현 검증, 현재 단면, 3D 모델 |
| ② 변경 미리보기 | 입력값을 바꾸는 즉시 변경 전후 단면과 간격·순간격·배근폭·판정(OK/NG)·단면적·중량 갱신 |
| ③ 결과 | 저장된 IFC를 다시 읽어 속성 변경 내역, 3D 모델, 단면 표시. 검증 로그 포함 |

**안전장치**
- 순간격 부족이나 늑근·피복 침범(NG)이면 실행 버튼이 비활성화되고 사유가 표시됩니다.
- 저장 경로가 원본 파일과 같으면 실행되지 않습니다(원본 보호).
- 결과 파일이 Tekla나 뷰어에서 열려 있어 저장할 수 없으면 안내 메시지를 띄웁니다.

| 메인 · 미리보기 | 변경 중(진행 표시) | 결과 |
|---|---|---|
| ![](docs/ui_2_preview.png) | ![](docs/ui_3_progress.png) | ![](docs/ui_4_result.png) |

### 2.2 명령줄 (CLI)

`run_cli.bat`을 실행하거나 아래 명령을 직접 입력합니다.

```bash
# 1) 배근 변경 (기본값: D19, 5개, 자동 등간격, 피복 40mm, 상·하부 모두)
python src/modify_rebar.py input/girder_rebar.ifc output/girder_rebar_D19x5.ifc --report output/change_report.json

# 간격 직접 지정 예: 중심간격 55mm
python src/modify_rebar.py input/girder_rebar.ifc output/girder_rebar_D19x5_s55.ifc --spacing 55

# 2) 결과 검증 + 단면 비교 이미지
python src/verify_rebar.py input/girder_rebar.ifc output/girder_rebar_D19x5.ifc --png docs/section_before_after.png
```

### 옵션 (`modify_rebar.py`)

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

## 3. 폴더 구성

```
├─ START_Mac.command / STOP_Mac.command     # ★ macOS 실행(켜져 있으면 재시작) / 종료
├─ START_Windows.bat / STOP_Windows.bat     # ★ Windows 실행 / 종료
├─ launcher.py            # 실행기: 시작/재시작/종료, 브라우저 열기 (전용 Python 설치는 START 파일이 담당)
├─ run_cli.bat            # 명령줄 일괄 실행
├─ src/
│  ├─ app.py              # 프로그램 화면 (Streamlit) - 아래 두 모듈을 그대로 호출
│  ├─ modify_rebar.py     # 분석 → 배근 계산 → IFC 갱신 (핵심 로직, CLI 겸용)
│  └─ verify_rebar.py     # 결과 IFC 독립 검증 + 단면 비교 이미지
├─ input/girder_rebar.ifc               # 제공된 원본
├─ output/
│  ├─ girder_rebar_D19x5.ifc            # ★ 결과 IFC
│  ├─ change_report.json                # 변경 내역
│  └─ verify_log.txt                    # 검증 로그
├─ docs/
│  ├─ section_before_after.png          # 단면 비교 캡처
│  ├─ ui_2_preview.png, ui_3_progress.png, ui_4_result.png   # 화면 캡처
│  └─ AI_활용_및_접근방식.md
├─ requirements.txt
```

---

## 4. 도메인 분석

### 4.1 원본 모델 구조 (IFC2X3, 단위 mm)

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

### 4.2 주근 배치 규칙 (원본에서 역산 → 재현 검증)

늑근(D13, Ø12.7)의 굽힘 중심선 반경은 33.85 mm이므로 **굽힘 내반경은 33.85 − 6.35 = 27.5 mm**입니다. 모서리 주근은 늑근 평탄부 위에 놓인 채 굽힘부 안쪽에 밀착됩니다. 굽힘 내반경(27.5)이 주근 반경(11.1 또는 9.55)보다 크므로, 주근 중심은 굽힘 중심과 같은 수직선에 놓입니다.

```
폭 방향 끝 주근 중심 = 보 측면 + 피복(40) + 늑근 직경(12.7) + 굽힘 내반경(27.5) = 측면 + 80.2
높이 방향 주근 중심 = 보 상·하면 ∓ (피복 40 + 늑근 12.7 + 주근 반경)
중간 주근          = 양 끝 사이 (n−1) 등분
```

원본 D22×4에 이 식을 적용하면 Tekla 좌표가 **오차 0.000 mm로 재현**됩니다.
(X = 5880.2 / 5960.07 / 6039.93 / 6119.8, Z = 5263.8 / 5936.2. 스크립트가 매 실행마다 먼저 이 재현 검증을 수행합니다.)

### 4.3 D19×5 적용 결과

- 유효 배근 폭 = 400 − 2×80.2 = **239.6 mm** → 중심간격 239.6 / 4 = **59.9 mm**
- 순간격 = 59.9 − 19.1 = **40.8 mm** ≥ max(25, 1.0·d<sub>b</sub>=19.1, 4/3×25=33.3) = 33.3 mm → **1단 배근 가능** (KDS 14 20 50)
- Z: 하부 5200 + 40 + 12.7 + 9.55 = **5262.25**, 상부 6000 − 62.25 = **5937.75**
- 늑근과는 접촉(간섭 0) 상태로, 원본 Tekla 배근과 같은 방식입니다.

## 5. IFC 갱신 내용

| 구분 | 갱신 항목 |
|---|---|
| 형상 | `IfcSweptDiskSolid` 반경 11.1 → 9.55, MappedItem 4 → 5개, 오프셋 0/59.9/…/239.6. RepresentationMap 1개를 공유해 중복을 없앴고, 프레젠테이션 레이어와 스타일(색상)은 유지 |
| 배치 | `IfcLocalPlacement` 원점 Z 재계산 (첫 철근 기준) |
| IFC 속성 | `NominalDiameter` 19.1, `CrossSectionArea` 286.5 mm², `BarLength`, `BarRole` = MAIN |
| Tekla Pset | Size 19, Number of bars in group 5, Weight / Weight total in group, Spacing exact `4*60`, Spacing target 59.9 |
| Assembly | Cast unit rebar weight 175.3 → 164.8 kg (주근 중량 증감 반영) |
| 정리 | 구 형상 엔티티 제거 (다른 객체가 참조하지 않는 것만) |

**구현상 주의점:** Tekla는 같은 `IfcPropertySingleValue` 인스턴스(예: `Size`, `Number of bars in group`, `Spacing exact`)를 여러 철근의 Pset이 공유합니다. 값을 직접 바꾸면 다른 철근까지 바뀌므로, 새 속성 객체를 만들어 해당 Pset에서만 교체합니다. GlobalId는 유지되므로 원본 객체 추적이 가능합니다.

## 6. 검증 (`verify_rebar.py`)

계산 로직을 재사용하지 않고, 결과 IFC의 **실제 3D 메시**를 다시 생성해 측정합니다.

1. 스키마 유효성. 결과 파일은 오류 5건 → 3건으로 줄었습니다. 남은 3건은 원본 Tekla 출력에 있던 것(Pset_BeamCommon의 빈 IfcBoolean 2건, 늑근 CrossSectionArea 누락)으로, 주근 범위 밖이라 손대지 않았습니다.
2. 형상과 메타데이터 일치: 메시 직경, 메시 개수 ↔ NominalDiameter, Size, Number of bars
3. 피복: 주근 표면 ~ 보 표면 ≥ 40 + 12.7
4. 등간격 및 최소 순간격
5. 늑근 간섭 여부

결과는 `output/verify_log.txt`에 있으며, 변경 전후 모두 **PASS**입니다.

## 7. 가정 및 한계

- 정착길이(상부 1570 / 하부 1210)는 참고자료의 구조일반사항 값을 그대로 유지했습니다. 실제 설계에서는 인장정착길이가 철근 직경에 비례하므로(l<sub>d</sub> ∝ d<sub>b</sub>), D19로 바꾸면 정착길이를 줄일 여지가 있습니다. 필요하면 길이 재계산 옵션으로 확장할 수 있습니다.
- 주근 단면적 비교: 4-D22 = 1548 mm², 5-D19 = 1433 mm²(약 −7.5%)입니다. 구조 검토(휨 내력)는 과제 범위 밖이라 수행하지 않았습니다.
- 늑근(D13@193)은 변경 대상이 아니므로 그대로 둡니다.
- 1개 보 / 직선 주근 세트를 대상으로 하며, 여러 보가 있는 모델은 보별 반복으로 확장할 수 있도록 함수 단위로 분리했습니다.
