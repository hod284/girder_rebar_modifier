"""
보 주근 배근 변경 시스템 - 화면 (Streamlit)

실행: START_Mac.command / START_Windows.bat 더블클릭 (켜져 있으면 재시작)  /  또는  streamlit run src/app.py

흐름
  왼쪽 패널: ① 입력 IFC 선택(찾아보기) → ② 변경값 입력(직경·개수·간격) → ③ 저장 위치 지정 → [변경 실행]
  본문 탭  : 모델 분석 / 변경 미리보기(입력 즉시 갱신) / 결과
배근 계산·IFC 수정은 modify_rebar.py, 검증은 verify_rebar.py 를 그대로 호출한다 (CLI 와 동일 로직).
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as uel
import ifcopenshell.util.unit

sys.path.insert(0, str(Path(__file__).parent))
import modify_rebar as mr  # noqa: E402
import verify_rebar as vr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "input" / "girder_rebar.ifc"
DEFAULT_OUT = ROOT / "output"
POS_KR = {"TOP": "상부근", "BOTTOM": "하부근"}
C_BEAM, C_STIR, C_MAIN, C_NEW, C_NG = "#e4e4e4", "#5b9722", "#1e4383", "#d9480f", "#c92a2a"

st.set_page_config(page_title="보 주근 배근 변경 시스템", page_icon="🏗️", layout="wide")
st.markdown("""<style>
section[data-testid="stSidebar"] {min-width: 400px; max-width: 460px;}
div.stButton > button[kind="primary"] {font-size: 1.05rem; font-weight: 700; height: 3rem;}
</style>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# 컴퓨터 파일/폴더 선택 창 (별도 프로세스에서 tkinter 실행 → OS 상관없이 안전)
# --------------------------------------------------------------------------- #
_DIALOG = r"""
import sys, tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True); r.update()
kind, init = sys.argv[1], sys.argv[2]
if kind == "file":
    p = filedialog.askopenfilename(parent=r, title="입력 IFC 파일 선택", initialdir=init,
                                   filetypes=[("IFC 파일", "*.ifc"), ("모든 파일", "*.*")])
else:
    p = filedialog.askdirectory(parent=r, title="결과 IFC 저장 폴더 선택", initialdir=init)
r.destroy()
sys.stdout.buffer.write((p or "").encode("utf-8"))
"""


def native_dialog(kind: str, init: str) -> str | None:
    """컴퓨터의 파일/폴더 선택 창. Mac: Finder 기본 창(osascript), Windows·Linux: tkinter."""
    init = init if init and Path(init).exists() else str(Path.home())
    err = "파일 선택 창을 열 수 없습니다. 경로를 직접 입력하세요."
    try:
        if platform.system() == "Darwin":
            loc = init.replace('"', '\\"')
            if kind == "file":
                script = (f'POSIX path of (choose file with prompt "입력 IFC 파일 선택" '
                          f'default location (POSIX file "{loc}"))')
            else:
                script = (f'POSIX path of (choose folder with prompt "결과 IFC 저장 폴더 선택" '
                          f'default location (POSIX file "{loc}"))')
            r = subprocess.run(["osascript", "-e", 'tell application "System Events" to activate',
                                "-e", script], capture_output=True, timeout=600)
            if r.returncode != 0:
                if b"-128" not in r.stderr:  # -128 = 사용자가 취소
                    st.session_state["dialog_err"] = err
                return None
            out = r.stdout.decode("utf-8").strip()
        else:
            r = subprocess.run([sys.executable, "-c", _DIALOG, kind, init], capture_output=True, timeout=600)
            if r.returncode != 0:
                st.session_state["dialog_err"] = err
                return None
            out = r.stdout.decode("utf-8").strip()
        return str(Path(out)) if out else None
    except Exception:  # noqa: BLE001
        st.session_state["dialog_err"] = err
        return None


def pick_input():
    cur = st.session_state.get("in_path", "")
    p = native_dialog("file", str(Path(cur).parent) if cur else str(ROOT / "input"))
    if p:
        st.session_state["in_path"] = p


def pick_outdir():
    p = native_dialog("dir", st.session_state.get("out_dir", str(DEFAULT_OUT)))
    if p:
        st.session_state["out_dir"] = p


def reset_all():
    st.session_state.clear()
    st.cache_data.clear()


def open_folder(path: str):
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # noqa: S606
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# 데이터 준비
# --------------------------------------------------------------------------- #
def open_ifc(data: bytes):
    return ifcopenshell.file.from_string(data.decode("utf-8", errors="replace"))


@st.cache_data(show_spinner=False)
def analyze_bytes(data: bytes):
    f = open_ifc(data)
    beam, stirrup, mains = mr.analyze(f)
    asm = f.by_type("IfcElementAssembly")
    asm_ps = uel.get_psets(asm[0]).get("Tekla Assembly", {}) if asm else {}
    bars = []
    for mi in mains:
        b = next(x for x in f.by_type("IfcReinforcingBar") if x.GlobalId == mi.guid)
        bl = uel.get_psets(b).get("Tekla Reinforcement - Bending List", {})
        bars.append({**mi.__dict__, "weight_group": bl.get("Weight total in group"),
                     "grade": bl.get("Grade"), "ifc_id": b.id()})
    st_bar = next(x for x in f.by_type("IfcReinforcingBar") if x.GlobalId == stirrup.guid)
    st_ps = uel.get_psets(st_bar)
    return {
        "beam": beam.__dict__, "stirrup": stirrup.__dict__, "mains": bars,
        "stirrup_count": st_ps.get("Tekla Reinforcement - Bending List", {}).get("Number of bars in group"),
        "stirrup_spacing": st_ps.get("Tekla Reinforcement - General", {}).get("Spacing target"),
        # Tekla 미번호(Numbering 전) 표시 "(?)" 는 화면에서 제거
        "assembly": {"mark": (asm_ps.get("Assembly/Cast unit Mark") or "").replace("(?)", "").strip() or None,
                     "position": asm_ps.get("Assembly/Cast unit position code"),
                     "rebar_weight": asm_ps.get("Cast unit rebar weight")},
        "schema": f.schema,
        "header_app": f.header.file_name.originating_system,
    }


@st.cache_data(show_spinner=False)
def meshes_bytes(data: bytes):
    f = open_ifc(data)
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    scale = ifcopenshell.util.unit.calculate_unit_scale(f)
    out = []
    for p in f.by_type("IfcBeam") + f.by_type("IfcReinforcingBar"):
        sh = ifcopenshell.geom.create_shape(s, p)
        v = np.array(sh.geometry.verts).reshape(-1, 3) / scale
        fc = np.array(sh.geometry.faces).reshape(-1, 3)
        kind = "beam" if p.is_a("IfcBeam") else ("main" if mr.is_straight_bar(p) else "stirrup")
        out.append((f"{p.is_a()} #{p.id()}", kind, v, fc))
    return out


def layouts_for(info, size, count, cover, agg, position, spacing):
    beam = mr.BeamInfo(**info["beam"])
    stirrup = mr.StirrupInfo(**info["stirrup"])
    res = {}
    for m in info["mains"]:
        if position != "BOTH" and m["position"] != position:
            continue
        lay = mr.compute_layout(beam, stirrup, m["position"], size, count, cover, agg, spacing)
        res[m["position"]] = (lay, mr.check_layout(lay, agg))
    return res


# --------------------------------------------------------------------------- #
# 그림
# --------------------------------------------------------------------------- #
def _rounded_rect(x0, z0, x1, z1, r, n=10):
    pts = []
    for cx, cz, a0 in [(x1 - r, z0 + r, -90), (x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180)]:
        for t in np.linspace(np.radians(a0), np.radians(a0 + 90), n):
            pts.append((cx + r * np.cos(t), cz + r * np.sin(t)))
    return "M " + " L ".join(f"{x:.2f},{z:.2f}" for x, z in pts) + " Z"


def section_figure(info, bars, cover, title, zoom=None):
    """bars: [(x, z, diameter, color)]"""
    b, s = info["beam"], info["stirrup"]
    x0, x1, z0, z1 = b["x_min"], b["x_max"], b["z_min"], b["z_max"]
    ds, ri = s["diameter"], s["bend_radius_inner"]
    shapes = [dict(type="rect", x0=x0, y0=z0, x1=x1, y1=z1, fillcolor=C_BEAM, line=dict(color="#444", width=1.5)),
              dict(type="path", path=_rounded_rect(x0 + cover, z0 + cover, x1 - cover, z1 - cover, ri + ds),
                   fillcolor=C_STIR, line=dict(width=0)),
              dict(type="path", path=_rounded_rect(x0 + cover + ds, z0 + cover + ds, x1 - cover - ds,
                                                   z1 - cover - ds, max(ri, 0.1)),
                   fillcolor=C_BEAM, line=dict(width=0)),
              dict(type="rect", x0=x0 + cover, y0=z0 + cover, x1=x1 - cover, y1=z1 - cover,
                   line=dict(color="#888", width=0.6, dash="dot"))]
    hx, hy, ht = [], [], []
    for x, z, d, color in bars:
        shapes.append(dict(type="circle", x0=x - d / 2, y0=z - d / 2, x1=x + d / 2, y1=z + d / 2,
                           fillcolor=color, line=dict(color="black", width=0.6)))
        hx.append(x)
        hy.append(z)
        ht.append(f"Ø{d}<br>X={x:.2f}<br>Z={z:.2f}")
    fig = go.Figure(go.Scatter(x=hx, y=hy, mode="markers", marker=dict(size=1, opacity=0),
                               hovertext=ht, hoverinfo="text", showlegend=False))
    fig.update_layout(shapes=shapes, title=dict(text=title, x=0.5, font=dict(size=15)),
                      margin=dict(l=10, r=10, t=45, b=10), plot_bgcolor="white", height=260 if zoom else 560)
    fig.update_yaxes(scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False)
    fig.update_xaxes(showgrid=False, zeroline=False, range=[x0 - (5 if zoom else 20), x1 + (5 if zoom else 20)])
    fig.update_yaxes(range=zoom if zoom else [z0 - 20, z1 + 20])
    return fig


def figure_3d(meshes, title):
    style = {"beam": ("#9e9e9e", 0.12, "보(콘크리트)"), "main": (C_MAIN, 1.0, "주근"), "stirrup": (C_STIR, 1.0, "늑근")}
    traces, shown = [], set()
    for name, kind, v, fc in meshes:
        color, op, label = style[kind]
        traces.append(go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=fc[:, 0], j=fc[:, 1], k=fc[:, 2],
                                color=color, opacity=op, name=label, hovertext=name, hoverinfo="text",
                                showlegend=kind not in shown,
                                lighting=dict(ambient=0.55, diffuse=0.8, specular=0.2)))
        shown.add(kind)
    fig = go.Figure(traces)
    fig.update_layout(title=dict(text=title, x=0.5), height=560, margin=dict(l=0, r=0, t=40, b=0),
                      scene=dict(aspectmode="manual", aspectratio=dict(x=0.45, y=2.4, z=0.8),
                                 xaxis_title="X", yaxis_title="Y", zaxis_title="Z",
                                 camera=dict(eye=dict(x=2.3, y=-1.3, z=1.0))),
                      legend=dict(orientation="h", y=0.02))
    return fig


# --------------------------------------------------------------------------- #
# 왼쪽 패널: 입력 → 변경값 → 저장 위치 → 실행
# --------------------------------------------------------------------------- #
ss = st.session_state
ss.setdefault("in_path", str(SAMPLE) if SAMPLE.exists() else "")
ss.setdefault("out_dir", str(DEFAULT_OUT))

with st.sidebar:
    st.button("🔄 초기화 (처음 상태로)", on_click=reset_all, width="stretch",
              help="입력값·결과를 모두 지우고 처음 상태로 되돌립니다. 프로그램 자체 재시작은 START 파일을 다시 실행하세요.")

    st.header("① 입력 IFC 파일")
    st.text_input("파일 경로", key="in_path", placeholder="C:\\...\\girder_rebar.ifc")
    st.button("📂 컴퓨터에서 IFC 파일 찾기", on_click=pick_input, width="stretch", key="btn_in")
    if ss.get("dialog_err"):
        st.warning(ss.pop("dialog_err"))

    st.header("② 변경할 값 입력")
    sizes = sorted(mr.KS_D3504)
    size = st.selectbox("주근 직경 (KS D 3504)", sizes, index=sizes.index(19),
                        format_func=lambda s: f"D{s}  (공칭지름 {mr.KS_D3504[s][0]} mm)")
    count = int(st.number_input("주근 개수 (상·하부 각각)", min_value=2, max_value=12, value=5, step=1))
    sp_mode = st.radio("주근 간격", ["자동 (유효폭 등간격)", "직접 입력"], horizontal=True)
    spacing = None
    if sp_mode == "직접 입력":
        spacing = float(st.number_input("중심간격 (mm)", min_value=1.0, max_value=1000.0, value=59.9, step=0.1,
                                        format="%.1f", help="보 중심을 기준으로 좌우 대칭 배치합니다."))
    sp_hint = st.empty()  # 입력 가능 범위 안내 (모델 분석 후 채움)
    position = st.radio("적용 대상", ["BOTH", "TOP", "BOTTOM"], horizontal=True,
                        format_func=lambda p: {"BOTH": "상·하부", "TOP": "상부근만", "BOTTOM": "하부근만"}[p])
    with st.expander("설계 기준값"):
        cover = st.number_input("피복두께 (mm)", 10.0, 100.0, 40.0, 5.0)
        agg = st.number_input("굵은골재 최대치수 (mm)", 10.0, 40.0, 25.0, 5.0)

    st.header("③ 결과 저장 위치")
    in_stem = Path(ss["in_path"]).stem if ss["in_path"] else "result"
    auto_name = f"{in_stem}_D{size}x{count}.ifc"
    if "out_name" not in ss or ss["out_name"] == ss.get("out_name_auto"):
        ss["out_name"] = auto_name
    ss["out_name_auto"] = auto_name
    st.text_input("저장 폴더", key="out_dir")
    st.button("📁 저장할 폴더 선택", on_click=pick_outdir, width="stretch", key="btn_out")
    st.text_input("파일 이름", key="out_name")
    out_path = Path(ss["out_dir"]) / (ss["out_name"] if ss["out_name"].lower().endswith(".ifc")
                                      else ss["out_name"] + ".ifc")
    st.caption(f"저장 경로: `{out_path}`")

# --------------------------------------------------------------------------- #
# 본문
# --------------------------------------------------------------------------- #
st.title("🏗️ 보 주근 배근 변경 시스템")
st.caption("IFC 보 모델의 주근(상부근·하부근)을 분석하고, 입력한 직경·개수·간격으로 재배치한 새 IFC 파일을 만듭니다.")

in_path = Path(ss["in_path"]) if ss["in_path"] else None
if not in_path or not in_path.is_file():
    st.info("왼쪽 **① 입력 IFC 파일**에서 **📂 컴퓨터에서 IFC 파일 찾기**를 눌러 원본 IFC 파일을 선택하세요.")
    st.stop()
data = in_path.read_bytes()
try:
    info = analyze_bytes(data)
except Exception as e:  # noqa: BLE001
    st.error(f"모델 분석 실패: {e}")
    st.stop()
B, S = info["beam"], info["stirrup"]

lays = layouts_for(info, size, count, cover, agg, position, spacing)
problems = [w for _, ws in lays.values() for w in ws]
import re as _re  # noqa: E402
short_problems = list(dict.fromkeys(_re.sub(r"^\[(TOP|BOTTOM)\]\s*", "", w) for w in problems))

# 입력 가능 범위 안내 한 줄
rng = mr.spacing_range(mr.BeamInfo(**B), mr.StirrupInfo(**S), size, count, cover, agg)
if rng["ok"]:
    range_line = (f"👉 D{size} {count}개 기준 입력 가능한 중심간격: **{np.ceil(rng['min'] * 10) / 10:.1f} ~ "
                  f"{np.floor(rng['max'] * 10) / 10:.1f} mm**  (자동 등간격 = {rng['max']:.1f} mm)")
else:
    range_line = (f"👉 D{size} {count}개는 이 보 폭에 1단으로 들어갈 수 없습니다. "
                  f"**개수를 {rng['max_count']}개 이하로** 줄이거나 더 가는 철근을 선택하세요.")
if spacing is not None:
    sp_hint.caption(range_line)
same_file = out_path.resolve() == in_path.resolve()

# 실행 버튼 + 진행 표시 영역
run_col, msg_col = st.columns([1.2, 4], vertical_alignment="center")
target = "상·하부" if position == "BOTH" else POS_KR[position]
sp_txt = "자동 등간격" if spacing is None else f"중심간격 {spacing:.0f}mm"
run = run_col.button("▶ 변경 실행", type="primary", width="stretch", disabled=bool(problems) or same_file)
if problems:
    msg_col.error("실행 불가: " + " / ".join(short_problems))
    msg_col.markdown(range_line)
elif same_file:
    msg_col.error("저장 경로가 입력 파일과 같습니다. 원본 보호를 위해 다른 이름으로 지정하세요.")
else:
    msg_col.markdown(f"**{target} 주근 → {count}-D{size}, {sp_txt}**  ·  저장: `{out_path}`")
progress_area = st.container()

res = ss.get("result")
if res:
    if res["errors"]:
        st.error(f"변경 완료, 검증 FAIL: {' / '.join(res['errors'])}  ·  `{res['path']}`")
    else:
        b1, b2 = st.columns([4, 1], vertical_alignment="center")
        b1.success(f"✅ 변경 완료 · 검증 PASS — 저장됨: `{res['path']}`  (아래 **결과** 탭에서 확인)")
        b2.button("📂 저장 폴더 열기", on_click=open_folder, args=(str(Path(res["path"]).parent),), width="stretch")

tab1, tab2, tab3 = st.tabs(["① 모델 분석", "② 변경 미리보기", "③ 결과"])

# ---------------- ① 모델 분석 ----------------
with tab1:
    st.subheader(f"`{in_path.name}`  ·  {info['schema']}  ·  {info['header_app'] or ''}")
    c = st.columns(5)
    c[0].metric(f"부재 ({info['assembly']['position'] or '-'})", f"{info['assembly']['mark'] or '-'}")
    c[1].metric("보 단면", f"{B['width']:.0f} × {B['height']:.0f}")
    c[2].metric(f"늑근 ({info['stirrup_count']}개)", f"D{round(S['diameter'])} @{int(info['stirrup_spacing'] or 0)}")
    c[3].metric("늑근 굽힘 내반경", f"{S['bend_radius_inner']:.1f} mm")
    c[4].metric("부재 철근 총중량", f"{info['assembly']['rebar_weight']} kg")
    st.markdown("#### 주근 정보")
    rows = [{"구분": POS_KR[m["position"]], "규격": f"{m['count']}-D{m['size']}", "등급": m["grade"],
             "공칭지름(mm)": m["diameter"], "개수": m["count"], "중심간격(mm)": m["spacing"],
             "순간격(mm)": round(m["spacing"] - m["diameter"], 2), "길이(mm)": m["length"],
             "Z(mm)": m["center_z"], "중량(kg)": m["weight_group"], "IFC": f"#{m['ifc_id']}"}
            for m in info["mains"]]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    ok = True
    for m in info["mains"]:
        lay = mr.compute_layout(mr.BeamInfo(**B), mr.StirrupInfo(**S), m["position"], m["size"], m["count"], cover, agg)
        ok &= max(abs(a - b) for a, b in zip(lay.centers_x, m["centers_x"])) < mr.TOL \
            and abs(lay.center_z - m["center_z"]) < mr.TOL
    if ok:
        st.success("배치 규칙 재현 검증 OK — 원본 주근 좌표가 '측면 + 피복 + 늑근 직경 + 굽힘 내반경' 규칙과 일치합니다.")
    else:
        st.warning("원본 좌표가 현재 피복두께 기준과 일치하지 않습니다. 설계 기준값을 확인하세요.")
    l, r = st.columns(2)
    with l:
        bars = [(x, m["center_z"], m["diameter"], C_MAIN) for m in info["mains"] for x in m["centers_x"]]
        st.plotly_chart(section_figure(info, bars, cover, "현재 단면"), width="stretch")
    with r:
        st.plotly_chart(figure_3d(meshes_bytes(data), "현재 3D 모델"), width="stretch")

# ---------------- ② 변경 미리보기 (입력 즉시 갱신) ----------------
with tab2:
    st.subheader(f"변경안: {target}  →  {count}-D{size}  ({sp_txt})")
    rows = []
    for m in info["mains"]:
        if m["position"] not in lays:
            continue
        lay, warns = lays[m["position"]]
        req = max(25.0, lay.diameter, 4 / 3 * agg)
        new_w = round(m["length"] / 1000 * mr.KS_D3504[size][1] * count, 1)
        rows.append({"구분": POS_KR[m["position"]], "변경 전": f"{m['count']}-D{m['size']}", "변경 후": f"{count}-D{size}",
                     "중심간격(mm)": f"{m['spacing']:.2f} → {lay.spacing:.2f}",
                     "순간격(mm)": f"{m['spacing'] - m['diameter']:.2f} → {lay.clear_spacing:.2f}",
                     "최소 순간격(mm)": round(req, 1),
                     "배근폭/유효폭(mm)": f"{lay.centers_x[-1] - lay.centers_x[0]:.1f} / {lay.limit_max - lay.limit_min:.1f}",
                     "판정": "NG ❌" if warns else "OK ✅",
                     "Z(mm)": f"{m['center_z']:.2f} → {lay.center_z:.2f}",
                     "단면적(mm²)": f"{m['count'] * mr.KS_D3504[m['size']][2]:.0f} → {count * mr.KS_D3504[size][2]:.0f}",
                     "중량(kg)": f"{m['weight_group']} → {new_w}"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if problems:
        st.error("기준 미달: " + " / ".join(short_problems))
        st.markdown(range_line)
    edge = next(iter(lays.values()))[0].edge_offset if lays else 0
    st.caption(f"끝 주근 한계 = 측면 + {cover:.0f}(피복) + {S['diameter']}(늑근) + "
               f"{max(S['bend_radius_inner'], mr.KS_D3504[size][0] / 2):.2f}(굽힘 내반경) = 측면 + {edge:.2f} mm  ·  "
               f"유효 배근폭 {B['width'] - 2 * edge:.1f} mm")
    before = [(x, m["center_z"], m["diameter"], C_MAIN) for m in info["mains"] for x in m["centers_x"]]
    after = []
    for m in info["mains"]:
        if m["position"] in lays:
            lay, warns = lays[m["position"]]
            after += [(x, lay.center_z, lay.diameter, C_NG if warns else C_NEW) for x in lay.centers_x]
        else:
            after += [(x, m["center_z"], m["diameter"], C_MAIN) for x in m["centers_x"]]
    zb, zt = [B["z_min"] - 5, B["z_min"] + 110], [B["z_max"] - 110, B["z_max"] + 5]
    c1, c2 = st.columns(2)
    for col, bars, name in [(c1, before, "변경 전"), (c2, after, "변경 후 (미리보기)")]:
        with col:
            st.plotly_chart(section_figure(info, bars, cover, name), width="stretch")
            st.plotly_chart(section_figure(info, bars, cover, f"{name} · 상부 확대", zoom=zt), width="stretch")
            st.plotly_chart(section_figure(info, bars, cover, f"{name} · 하부 확대", zoom=zb), width="stretch")

# ---------------- ③ 결과 ----------------
with tab3:
    if not res:
        st.info("아직 변경을 실행하지 않았습니다. 위의 **▶ 변경 실행** 버튼을 누르세요.")
    else:
        rep = res["report"]
        st.subheader(f"결과 파일: `{res['path']}`")
        c = st.columns(4)
        aw = rep.get("assembly_rebar_weight", {})
        a0 = rep["after"][0] if rep["after"] else None
        c[0].metric("변경 세트", f"{len(rep['after'])}개")
        c[1].metric("주근 규격", f"{a0['count']}-D{a0['size']}" if a0 else "-")
        c[2].metric("중심간격", f"{a0['spacing']:.2f} mm" if a0 else "-")
        c[3].metric("부재 철근 총중량", f"{aw.get('after', '-')} kg",
                    f"{aw['after'] - aw['before']:+.1f} kg" if aw else None, delta_color="off")
        st.markdown("#### IFC 속성 변경 내역")
        prow = []
        for a in rep["after"]:
            bef = next(m for m in rep["before"] if m["guid"] == a["guid"])
            prow.append({"구분": POS_KR[a["position"]], "GlobalId": a["guid"],
                         "NominalDiameter": f"{bef['diameter']} → {a['diameter']}",
                         "Size": f"{bef['size']} → {a['size']}",
                         "Number of bars": f"{bef['count']} → {a['count']}",
                         "Spacing exact": f"→ {a['count'] - 1}*{round(a['spacing'])}",
                         "Weight(개당)": f"→ {a['weight_each']}",
                         "Weight total": f"{a['old_weight_group']} → {a['weight_group']}"})
        st.dataframe(pd.DataFrame(prow), hide_index=True, width="stretch")
        out_bytes = Path(res["path"]).read_bytes() if Path(res["path"]).exists() else None
        if out_bytes:
            l, r = st.columns(2)
            with l:
                st.plotly_chart(figure_3d(meshes_bytes(out_bytes), "결과 3D 모델 (마우스로 회전/확대)"), width="stretch")
            with r:
                info2 = analyze_bytes(out_bytes)
                bars2 = [(x, m["center_z"], m["diameter"], C_NEW) for m in info2["mains"] for x in m["centers_x"]]
                st.plotly_chart(section_figure(info2, bars2, cover, "저장된 IFC에서 다시 읽은 단면"), width="stretch")
        with st.expander("검증 상세 로그"):
            st.code("\n".join(res["vlines"]), language="text")
        with st.expander("처리 로그"):
            st.code("\n".join(res["logs"]), language="text")

# --------------------------------------------------------------------------- #
# 변경 실행 (진행 표시)
# --------------------------------------------------------------------------- #
if run:
    with progress_area:
        with st.status("🔧 변경 중입니다... 잠시만 기다려 주세요.", expanded=True) as status:
            bar = st.progress(0, text="준비 중")
            logs = []
            try:
                steps = ["입력 IFC 읽는 중", "보·철근 분석 중", "주근 형상·속성 변경 중", "IFC 파일 저장 중",
                         "결과 파일 검증 중", "완료"]

                def step(i):
                    bar.progress(int(i / (len(steps) - 1) * 100), text=f"({i + 1}/{len(steps)}) {steps[i]}")
                    st.write(f"• {steps[i]}")
                    time.sleep(0.25)

                step(0)
                f = open_ifc(data)
                step(1)
                mr.analyze(f)
                step(2)
                report = mr.modify(f, size, count, cover, agg, position, log=logs.append, spacing=spacing)
                step(3)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                existed = out_path.exists()
                f.write(str(out_path))
                if existed:
                    st.write("  (같은 이름의 기존 파일을 덮어썼습니다)")
                step(4)
                _, errors, vlines = vr.verify(str(out_path), cover, agg)
                step(5)
                ss["result"] = dict(path=str(out_path), report=report, logs=logs, errors=errors, vlines=vlines)
                status.update(label="✅ 변경 완료" if not errors else "⚠️ 변경 완료 (검증 FAIL)",
                              state="complete" if not errors else "error")
            except PermissionError:
                status.update(label="❌ 저장 실패", state="error")
                st.error(f"파일을 저장할 수 없습니다. 다른 프로그램(Tekla, 뷰어 등)에서 열려 있는지, 폴더 권한을 확인하세요: {out_path}")
                st.stop()
            except Exception as e:  # noqa: BLE001
                status.update(label="❌ 변경 실패", state="error")
                st.exception(e)
                st.stop()
    time.sleep(0.6)
    st.rerun()
