"""
결과 IFC 검증 + 단면 비교 이미지 생성
=====================================
modify_rebar.py 의 계산 로직을 쓰지 않고, IFC 를 다시 열어 '실제 생성된 3D 메시'에서
주근 위치를 측정해 독립적으로 검증한다.

    python src/verify_rebar.py input/girder_rebar.ifc output/girder_rebar_D19x5.ifc --png output/section_before_after.png

검증 항목
  1. IFC 스키마 유효성 (ifcopenshell.validate)
  2. 형상 ↔ 메타데이터 일치: 메시 직경 = NominalDiameter, 메시 개수 = 'Number of bars in group', Size 속성
  3. 피복두께: 주근 표면 ~ 보 표면 ≥ 피복 + 늑근 직경
  4. 등간격 / 최소 순간격 (KDS 14 20 50)
  5. 늑근 간섭: 주근 단면이 늑근 튜브와 겹치지 않음
"""
import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as uel
import ifcopenshell.util.unit
import ifcopenshell.validate

TOL = 0.5  # mm (메시 테셀레이션 오차 허용)


def mesh(f, p):
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    sh = ifcopenshell.geom.create_shape(s, p)
    v = np.array(sh.geometry.verts).reshape(-1, 3) / ifcopenshell.util.unit.calculate_unit_scale(f)
    return v


def bar_sections(v, along=1, gap=5.0):
    """직선 주근 메시 → 단면 원(중심, 반경) 리스트. 폭(X) 방향으로 정점을 군집화."""
    xs = np.sort(np.unique(np.round(v[:, 0], 1)))
    groups, cur = [], [xs[0]]
    for x in xs[1:]:
        if x - cur[-1] > gap:
            groups.append(cur)
            cur = []
        cur.append(x)
    groups.append(cur)
    out = []
    for g in groups:
        sel = v[(v[:, 0] >= g[0] - 0.05) & (v[:, 0] <= g[-1] + 0.05)]
        cx, cz = (sel[:, 0].max() + sel[:, 0].min()) / 2, (sel[:, 2].max() + sel[:, 2].min()) / 2
        r = (sel[:, 0].max() - sel[:, 0].min()) / 2
        out.append((cx, cz, r))
    return out


def inspect(path, cover):
    f = ifcopenshell.open(path)
    beam = f.by_type("IfcBeam")[0]
    bv = mesh(f, beam)
    bx0, bx1, bz0, bz1 = bv[:, 0].min(), bv[:, 0].max(), bv[:, 2].min(), bv[:, 2].max()
    zmid = (bz0 + bz1) / 2
    stir, mains = None, []
    for b in f.by_type("IfcReinforcingBar"):
        ps = uel.get_psets(b).get("Tekla Reinforcement - Bending List", {})
        if str(ps.get("Shape")) == "1":
            mains.append((b, ps, mesh(f, b)))
        else:
            stir = (b, ps, mesh(f, b))
    # 첫 번째 늑근 하나의 단면(Y 범위가 가장 작은 쪽)
    # 늑근 세트는 모든 개체가 같은 XZ 단면을 가지므로, 전체 정점을 XZ 평면에 투영해 단면으로 사용
    sv1 = stir[2]
    rep = stir[0].Representation.Representations[0]
    solid = rep.Items[0].MappingSource.MappedRepresentation.Items[0]
    r_c = min(seg.ParentCurve.BasisCurve.Radius for seg in solid.Directrix.Segments
              if seg.ParentCurve.BasisCurve.is_a("IfcCircle"))
    return dict(f=f, beam=(bx0, bx1, bz0, bz1), zmid=zmid, stirrup=stir, stir_slice=sv1, mains=mains,
                stir_r_c=r_c)


def verify(path, cover, max_agg):
    d = inspect(path, cover)
    f = d["f"]
    errors, lines = [], []

    # 1. 스키마
    log = logging.getLogger("validate")
    log.setLevel(logging.ERROR)
    h = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(f, h)
    schema_err = [s for s in h.statements if s.get("level", "").lower() == "error"]
    lines.append(f"  스키마 검증: 오류 {len(schema_err)}건")
    for s in schema_err:
        inst = str(s.get("instance"))
        lines.append(f"    - {inst[:60]}... | {str(s.get('message')).splitlines()[0][:40]}")

    bx0, bx1, bz0, bz1 = d["beam"]
    ds = d["stirrup"][0].NominalDiameter
    sv = d["stir_slice"]
    for b, ps, v in d["mains"]:
        secs = bar_sections(v)
        pos = "TOP" if secs[0][1] > d["zmid"] else "BOTTOM"
        rs = [s[2] for s in secs]
        xs = [s[0] for s in secs]
        z = np.mean([s[1] for s in secs])
        dia = 2 * np.mean(rs)
        n_meta = int(ps["Number of bars in group"])
        sz = ps["Size"]
        lines.append(f"  [{pos}] 메시: {len(secs)}개, Ø{dia:.2f}, X={[round(float(x), 1) for x in xs]}, Z={z:.2f}")
        lines.append(f"         메타: Size={sz}, 개수={n_meta}, NominalDiameter={b.NominalDiameter}, "
                     f"CrossSectionArea={b.CrossSectionArea}, BarRole={b.BarRole}")
        # 2. 형상-메타 일치 (테셀레이션된 원은 다각형이라 지름이 약간 작게 측정될 수 있음)
        if abs(dia - b.NominalDiameter) > 1.0:
            errors.append(f"{pos}: 메시 직경 {dia:.2f} ≠ NominalDiameter {b.NominalDiameter}")
        if len(secs) != n_meta:
            errors.append(f"{pos}: 메시 개수 {len(secs)} ≠ 메타 {n_meta}")
        # 3. 피복
        r = b.NominalDiameter / 2
        side = min(min(xs) - r - bx0, bx1 - (max(xs) + r))
        vert = (bz1 - (z + r)) if pos == "TOP" else (z - r - bz0)
        need = cover + ds
        lines.append(f"         측면 순피복(주근표면) {side:.2f} / 상·하면 {vert:.2f}  (필요 ≥ {need:.1f})")
        if side < need - TOL or vert < need - TOL:
            errors.append(f"{pos}: 피복 부족")
        # 4. 간격
        sp = np.diff(xs)
        clear = sp.min() - b.NominalDiameter
        req = max(25.0, b.NominalDiameter, 4 / 3 * max_agg)
        lines.append(f"         중심간격 {np.round(sp, 2).tolist()}  순간격 {clear:.2f} (최소 {req:.1f})")
        if sp.max() - sp.min() > TOL:
            errors.append(f"{pos}: 등간격 아님")
        if clear < req - TOL:
            errors.append(f"{pos}: 순간격 부족")
        # 5. 늑근 간섭 (늑근 튜브 표면 정점과 주근 축 사이 거리 ≥ 주근 반경)
        pts = sv[:, [0, 2]]
        dmin = min(np.min(np.hypot(pts[:, 0] - x, pts[:, 1] - z)) for x in xs)
        lines.append(f"         늑근 표면까지 최소거리 {dmin:.2f} (주근 반경 {r:.2f}) → 여유 {dmin - r:.2f}")
        if dmin < r - TOL:
            errors.append(f"{pos}: 늑근과 간섭")
    return d, errors, lines


def plot(before, after, png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle, FancyBboxPatch

    def draw(ax, d, zoom=False):
        bx0, bx1, bz0, bz1 = d["beam"]
        ax.add_patch(Rectangle((bx0, bz0), bx1 - bx0, bz1 - bz0, fc="#e3e3e3", ec="#444", lw=1.2))
        # 늑근: 메시 단면의 외곽 경계 + 직경 + 굽힘반경으로 둥근 사각형 표시
        st = d["stirrup"][0]
        ds = st.NominalDiameter
        sv = d["stir_slice"]
        x0, x1, z0, z1 = sv[:, 0].min(), sv[:, 0].max(), sv[:, 2].min(), sv[:, 2].max()
        r_out = d["stir_r_c"] + ds / 2
        for off, fc in [(0, "#5b9722"), (ds, "#e3e3e3")]:
            r = max(r_out - off, 0.1)
            ax.add_patch(FancyBboxPatch((x0 + off + r, z0 + off + r), x1 - x0 - 2 * off - 2 * r,
                                        z1 - z0 - 2 * off - 2 * r, boxstyle=f"round,pad={r}",
                                        fc=fc, ec="none"))
        for b, ps, v in d["mains"]:
            secs = bar_sections(v)
            for cx, cz, _ in secs:
                ax.add_patch(Circle((cx, cz), b.NominalDiameter / 2, fc="#1e4383", ec="k", lw=0.5))
            if zoom and secs[0][1] < (bz0 + bz1) / 2:
                xs = [s_[0] for s_ in secs]
                sp = float(np.diff(xs).mean())
                ax.set_title(f"bottom bars: {len(xs)}-D{round(b.NominalDiameter)}  c/c {sp:.1f} mm, "
                             f"clear {sp - b.NominalDiameter:.1f} mm", fontsize=10)
                for cx in xs:
                    ax.plot([cx, cx], [bz0, bz0 + 15], c="#c00", lw=0.6)
        ax.set_aspect("equal")
        if zoom:
            ax.set_xlim(bx0 - 5, bx1 + 5)
            ax.set_ylim(bz0 - 5, bz0 + 110)
        else:
            ax.set_xlim(bx0 - 20, bx1 + 20)
            ax.set_ylim(bz0 - 20, bz1 + 20)
        ax.tick_params(labelsize=8)

    fig = plt.figure(figsize=(11, 12.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[3.2, 1])
    for col, (title, d) in enumerate([("BEFORE : top 4-D22 / bottom 4-D22", before),
                                      ("AFTER : top 5-D19 / bottom 5-D19", after)]):
        ax = fig.add_subplot(gs[0, col])
        draw(ax, d)
        ax.set_title(title, fontsize=12, weight="bold")
        draw(fig.add_subplot(gs[1, col]), d, zoom=True)
    fig.suptitle("Girder G0  400x800 section (cover 40 mm, stirrup D13, mm)", fontsize=13)
    fig.tight_layout()
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--cover", type=float, default=40.0)
    ap.add_argument("--max-aggregate", type=float, default=25.0)
    ap.add_argument("--png")
    a = ap.parse_args()
    results = {}
    total_err = 0
    for tag, p in [("BEFORE", a.before), ("AFTER", a.after)]:
        d, errs, lines = verify(p, a.cover, a.max_aggregate)
        results[tag] = d
        print(f"== {tag}: {p}")
        print("\n".join(lines))
        if tag == "AFTER":
            total_err = len(errs)
        print("  결과: " + ("PASS" if not errs else "FAIL\n    - " + "\n    - ".join(errs)))
    if a.png:
        plot(results["BEFORE"], results["AFTER"], a.png)
        print(f"[이미지] {a.png}")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
