"""
보 모델 분석 및 주근 배근 정보 변경 시스템
=========================================

IFC(IFC2X3, Tekla Structures 출력) 보 모델에서 주근(상부근/하부근)을 찾아
지정한 직경·개수로 등간격 재배치하고, 3D 형상과 메타데이터를 함께 갱신한다.

    python src/modify_rebar.py input/girder_rebar.ifc output/girder_rebar_D19x5.ifc --size 19 --count 5

배치 원리 (보 단면, 폭 방향)
---------------------------
  양 끝 주근 중심 = 보 측면 + 피복 + 늑근 직경 + 늑근 굽힘 내반경
    → 주근이 늑근 하부(상부) 평탄부에 놓인 채 모서리 굽힘부에 밀착되는 위치.
      (굽힘 내반경 ≥ 주근 반경이면 주근 중심은 굽힘 중심과 같은 수직선에 놓인다)
  높이 방향 주근 중심 = 보 상·하면 ∓ (피복 + 늑근 직경 + 주근 반경)
  사이 주근 = 양 끝 사이를 (n-1) 등분

원본 모델(D22×4)에 같은 식을 적용하면 Tekla 좌표(5880.2 / 79.87 간격 / Z 5263.8, 5936.2)가
그대로 재현되며, 스크립트는 실행 시 이 재현 검증을 먼저 수행한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as uel
import ifcopenshell.util.placement as upl
import ifcopenshell.util.unit

# KS D 3504 이형철근 제원: 호칭 -> (공칭지름 mm, 단위중량 kg/m, 공칭단면적 mm²)
KS_D3504 = {
    10: (9.53, 0.560, 71.33),
    13: (12.7, 0.995, 126.7),
    16: (15.9, 1.56, 198.6),
    19: (19.1, 2.25, 286.5),
    22: (22.2, 3.04, 387.1),
    25: (25.4, 3.98, 506.7),
    29: (28.6, 5.04, 642.4),
    32: (31.8, 6.23, 794.2),
}
TOL = 0.05  # mm


# --------------------------------------------------------------------------- #
# 데이터 구조
# --------------------------------------------------------------------------- #
@dataclass
class BeamInfo:
    guid: str
    name: str
    width: float
    height: float
    x_min: float  # 폭 방향(주근 분배 방향) 측면 좌표
    x_max: float
    z_min: float  # 보 하면
    z_max: float  # 보 상면
    length_axis: list


@dataclass
class StirrupInfo:
    guid: str
    diameter: float
    bend_radius_centerline: float
    bend_radius_inner: float


@dataclass
class MainBarInfo:
    guid: str
    position: str  # 'TOP' | 'BOTTOM'
    size: int
    diameter: float
    count: int
    length: float
    centers_x: list  # 폭 방향 중심 좌표 (전역)
    center_z: float
    spacing: float


@dataclass
class Layout:
    position: str
    size: int
    diameter: float
    count: int
    first_x: float
    last_x: float
    spacing: float
    clear_spacing: float
    center_z: float
    edge_offset: float
    centers_x: list = field(default_factory=list)
    limit_min: float = 0.0   # 주근 중심이 놓일 수 있는 폭 방향 한계 (늑근 안쪽)
    limit_max: float = 0.0
    spacing_mode: str = "AUTO"  # AUTO: 유효폭 등분 / MANUAL: 지정 간격, 보 중심 대칭


# --------------------------------------------------------------------------- #
# 1. 모델 분석
# --------------------------------------------------------------------------- #
def _geom_verts(ifc_file, product) -> np.ndarray:
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    shape = ifcopenshell.geom.create_shape(s, product)
    v = np.array(shape.geometry.verts).reshape(-1, 3)
    # geom 결과는 미터(SI)일 수 있으므로 모델 길이 단위(mm)로 환산
    unit = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)  # 모델단위 -> m
    return v / unit


def _bar_frame(bar):
    """(4x4 전역 배치행렬, 축방향, 분배방향) 반환. Tekla: 로컬 X=철근축, 로컬 Y=배근 분배방향."""
    m = upl.get_local_placement(bar.ObjectPlacement)
    return m, m[:3, 0], m[:3, 1]


def _body_rep(product):
    for rep in product.Representation.Representations:
        if rep.RepresentationIdentifier == "Body":
            return rep
    raise RuntimeError(f"{product} has no Body representation")


def _mapped_offsets(rep):
    """MappedRepresentation 의 각 MappedItem 로컬 오프셋(x,y,z)."""
    return [np.array(mi.MappingTarget.LocalOrigin.Coordinates, dtype=float) for mi in rep.Items]


def _source_solid(rep):
    solids = {mi.MappingSource.MappedRepresentation.Items[0] for mi in rep.Items}
    if len(solids) != 1:
        raise RuntimeError("주근 세트 내 형상이 서로 다릅니다(지원하지 않는 형태).")
    return solids.pop()


def is_straight_bar(bar) -> bool:
    rep = _body_rep(bar)
    if rep.RepresentationType != "MappedRepresentation":
        return False
    solid = rep.Items[0].MappingSource.MappedRepresentation.Items[0]
    return (solid.is_a("IfcSweptDiskSolid") and solid.Directrix.is_a("IfcTrimmedCurve")
            and solid.Directrix.BasisCurve.is_a("IfcLine"))


def analyze(f) -> tuple[BeamInfo, StirrupInfo, list]:
    beams = f.by_type("IfcBeam")
    if len(beams) != 1:
        raise RuntimeError(f"보 객체가 1개가 아닙니다: {len(beams)}")
    beam = beams[0]
    bars = f.by_type("IfcReinforcingBar")
    mains = [b for b in bars if is_straight_bar(b)]
    stirrups = [b for b in bars if b not in mains]
    if not mains or len(stirrups) != 1:
        raise RuntimeError("주근/늑근 식별 실패")

    # --- 보: 전역 형상에서 단면 경계 추출 ---
    _, axis0, dist0 = _bar_frame(mains[0])
    bv = _geom_verts(f, beam)
    proj_w = bv @ dist0
    prof = beam.Representation.Representations[0].Items[0].SweptArea
    beam_info = BeamInfo(
        guid=beam.GlobalId, name=beam.Name,
        width=float(prof.XDim), height=float(prof.YDim),
        x_min=float(proj_w.min()), x_max=float(proj_w.max()),
        z_min=float(bv[:, 2].min()), z_max=float(bv[:, 2].max()),
        length_axis=axis0.round(6).tolist(),
    )

    # --- 늑근: 직경, 굽힘반경 ---
    st = stirrups[0]
    st_rep = _body_rep(st)
    st_solid = st_rep.Items[0].MappingSource.MappedRepresentation.Items[0]
    radii = sorted({round(seg.ParentCurve.BasisCurve.Radius, 6)
                    for seg in st_solid.Directrix.Segments
                    if seg.ParentCurve.BasisCurve.is_a("IfcCircle")})
    r_c = radii[0]
    stirrup_info = StirrupInfo(st.GlobalId, float(st.NominalDiameter), r_c, r_c - st.NominalDiameter / 2)

    # --- 주근 ---
    zmid = (beam_info.z_min + beam_info.z_max) / 2
    main_infos = []
    for b in mains:
        m, ax, dist = _bar_frame(b)
        rep = _body_rep(b)
        solid = _source_solid(rep)
        centers = [m[:3, :3] @ o + m[:3, 3] for o in _mapped_offsets(rep)]
        xs = sorted(float(c @ dist0) for c in centers)
        z = float(np.mean([c[2] for c in centers]))
        bl = uel.get_psets(b).get("Tekla Reinforcement - Bending List", {})
        size = int(bl.get("Size", round(b.NominalDiameter)))
        main_infos.append(MainBarInfo(
            guid=b.GlobalId, position="TOP" if z > zmid else "BOTTOM",
            size=size, diameter=float(b.NominalDiameter), count=len(centers),
            length=float(solid.EndParam - solid.StartParam),
            centers_x=[round(x, 3) for x in xs], center_z=round(z, 3),
            spacing=round((xs[-1] - xs[0]) / (len(xs) - 1), 3) if len(xs) > 1 else 0.0,
        ))
    main_infos.sort(key=lambda i: i.position)
    return beam_info, stirrup_info, main_infos


# --------------------------------------------------------------------------- #
# 2. 배근 계산
# --------------------------------------------------------------------------- #
def compute_layout(beam: BeamInfo, st: StirrupInfo, position: str, size: int, count: int,
                   cover: float, max_aggregate: float, spacing: float | None = None) -> Layout:
    """spacing=None → 유효폭을 (n-1) 등분(자동). spacing 지정 → 그 중심간격으로 보 중심에 대칭 배치."""
    db, _, _ = KS_D3504[size]
    rb = db / 2
    # 폭 방향: 늑근 내면 + 모서리 굽힘에 밀착 (굽힘 내반경 < 주근 반경이면 주근 반경 사용)
    edge = cover + st.diameter + max(st.bend_radius_inner, rb)
    lim_min = beam.x_min + edge
    lim_max = beam.x_max - edge
    mode = "AUTO" if not spacing else "MANUAL"
    if mode == "AUTO":
        first, last = lim_min, lim_max
        spacing = (last - first) / (count - 1) if count > 1 else 0.0
    else:
        mid = (beam.x_min + beam.x_max) / 2
        first = mid - spacing * (count - 1) / 2
        last = mid + spacing * (count - 1) / 2
    # 높이 방향: 늑근 평탄부 위에 안착
    off_v = cover + st.diameter + rb
    z = beam.z_max - off_v if position == "TOP" else beam.z_min + off_v
    centers = [first + i * spacing for i in range(count)]
    if count == 1:
        centers = [(beam.x_min + beam.x_max) / 2]
    return Layout(position, size, db, count, first, last, spacing,
                  spacing - db if count > 1 else float("inf"), z, edge, centers,
                  lim_min, lim_max, mode)


def spacing_range(beam: BeamInfo, st: StirrupInfo, size: int, count: int, cover: float,
                  max_aggregate: float) -> dict:
    """직접 입력 가능한 중심간격 범위와, 1단 배근 가능한 최대 개수.
    최소 = 최소 순간격 + 주근 직경 (KDS 14 20 50), 최대 = 유효 배근폭 / (n-1) (늑근·피복 침범 방지)."""
    db = KS_D3504[size][0]
    edge = cover + st.diameter + max(st.bend_radius_inner, db / 2)
    width = (beam.x_max - beam.x_min) - 2 * edge          # 유효 배근폭 (끝 주근 중심 간 최대 거리)
    s_min = max(25.0, db, 4.0 / 3.0 * max_aggregate) + db
    s_max = width / (count - 1) if count > 1 else float("inf")
    max_count = int(width // s_min) + 1 if s_min > 0 else count
    return {"min": s_min, "max": s_max, "ok": s_min <= s_max + 1e-9, "max_count": max_count, "width": width}


def check_layout(lay: Layout, max_aggregate: float) -> list[str]:
    """KDS 14 20 50 철근 최소 순간격: max(25mm, 1.0db, 굵은골재 최대치수의 4/3)."""
    req = max(25.0, lay.diameter, 4.0 / 3.0 * max_aggregate)
    msgs = []
    if lay.count > 1 and lay.clear_spacing + 1e-6 < req:
        msgs.append(f"[{lay.position}] 순간격 {lay.clear_spacing:.1f}mm < 최소 {req:.1f}mm → 1단 배근 불가")
    if lay.limit_max > lay.limit_min and (lay.centers_x[0] < lay.limit_min - 0.01
                                          or lay.centers_x[-1] > lay.limit_max + 0.01):
        msgs.append(f"[{lay.position}] 배근폭 {lay.centers_x[-1] - lay.centers_x[0]:.1f}mm > "
                    f"유효 배근폭 {lay.limit_max - lay.limit_min:.1f}mm → 늑근·피복 침범")
    return msgs


# --------------------------------------------------------------------------- #
# 3. IFC 갱신
# --------------------------------------------------------------------------- #
def _remove_if_orphan(f, ents):
    """다른 곳에서 참조되지 않는 엔티티만 제거 (Tekla 는 곡선/벡터를 많이 공유하므로 안전하게)."""
    changed = True
    ents = [e for e in ents if e is not None]
    while changed:
        changed = False
        for e in list(ents):
            try:
                if f.get_total_inverses(e) == 0:
                    f.remove(e)
                    ents.remove(e)
                    changed = True
            except RuntimeError:
                ents.remove(e)


def _set_prop(f, pset, name, value):
    """속성값 교체. Tekla 는 동일 IfcPropertySingleValue 를 여러 Pset 이 공유하므로
    기존 객체를 수정하지 않고 새 속성을 만들어 해당 Pset 에서만 교체한다."""
    props = list(pset.HasProperties)
    for i, p in enumerate(props):
        if p.Name == name:
            new = f.createIfcPropertySingleValue(name, p.Description, value, p.Unit)
            props[i] = new
            pset.HasProperties = props
            _remove_if_orphan(f, [p])
            return new
    raise KeyError(f"{pset.Name}.{name} not found")


def _pset(f, product, name):
    for rel in product.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.Name == name:
            return rel.RelatingPropertyDefinition
    return None


def apply_layout(f, bar, lay: Layout, d_hat: np.ndarray):
    size, count = lay.size, lay.count
    db, unit_w, area = KS_D3504[size]
    m, ax, dist = _bar_frame(bar)
    old_rep = _body_rep(bar)
    old_items = list(old_rep.Items)
    old_solid = _source_solid(old_rep)
    length = old_solid.EndParam - old_solid.StartParam
    # 이 철근의 분배방향(로컬 Y)이 기준축과 반대면, 오프셋 0 인 첫 철근은 반대쪽 끝에 놓인다
    dist_sign = 1.0 if float(dist @ d_hat) > 0 else -1.0

    # (a) 배치: 원점을 '첫 번째 주근' 위치로 이동 (축방향 성분은 유지)
    origin_old = m[:3, 3]
    first_global = lay.first_x if dist_sign > 0 else lay.last_x
    new_origin = origin_old + d_hat * (first_global - origin_old @ d_hat)
    new_origin[2] = lay.center_z
    parent = bar.ObjectPlacement.PlacementRelTo
    pm = upl.get_local_placement(parent) if parent else np.eye(4)
    rel_origin = np.linalg.inv(pm) @ np.append(new_origin, 1.0)
    old_pt = bar.ObjectPlacement.RelativePlacement.Location
    bar.ObjectPlacement.RelativePlacement.Location = f.createIfcCartesianPoint(
        tuple(float(round(c, 6)) for c in rel_origin[:3]))
    _remove_if_orphan(f, [old_pt])

    # (b) 형상: 새 직경의 SweptDiskSolid 1개 + RepresentationMap 1개 + MappedItem n개
    ctx = old_rep.ContextOfItems
    trimmed = f.createIfcTrimmedCurve(
        old_solid.Directrix.BasisCurve,
        (f.create_entity("IfcParameterValue", 0.0),),
        (f.create_entity("IfcParameterValue", float(length)),), True, "PARAMETER")
    solid = f.createIfcSweptDiskSolid(trimmed, db / 2.0, None, 0.0, float(length))
    for si in old_solid.StyledByItem or []:
        f.createIfcStyledItem(solid, si.Styles, si.Name)
    src_rep = f.createIfcShapeRepresentation(ctx, "Body", "AdvancedSweptSolid", (solid,))
    origin_ax = old_items[0].MappingSource.MappingOrigin
    rmap = f.createIfcRepresentationMap(origin_ax, src_rep)
    items = []
    for i in range(count):
        off = f.createIfcCartesianPoint((0.0, float(round(i * lay.spacing, 6)), 0.0))
        op = f.createIfcCartesianTransformationOperator3D(None, None, off, None, None)
        items.append(f.createIfcMappedItem(rmap, op))
    new_rep = f.createIfcShapeRepresentation(ctx, "Body", "MappedRepresentation", items)

    pds = bar.Representation
    pds.Representations = [new_rep if r == old_rep else r for r in pds.Representations]
    for layer in old_rep.LayerAssignments or []:
        layer.AssignedItems = [new_rep if r == old_rep else r for r in layer.AssignedItems]

    # 구 형상 정리
    old_maps = [mi.MappingSource for mi in old_items]
    old_reps = [mp.MappedRepresentation for mp in old_maps]
    old_ops = [mi.MappingTarget for mi in old_items]
    old_ops_pts = [op.LocalOrigin for op in old_ops]
    old_styles = list(old_solid.StyledByItem or [])
    old_dir = old_solid.Directrix
    f.remove(old_rep)
    for e in old_items:
        f.remove(e)
    _remove_if_orphan(f, old_maps + old_reps + old_ops + old_ops_pts + old_styles + [old_solid, old_dir])

    # (c) IFC 표준 속성
    bar.NominalDiameter = float(db)
    bar.CrossSectionArea = float(area)
    bar.BarLength = float(length)
    bar.BarRole = "MAIN"

    # (d) Tekla 속성(Pset)
    w_each = round(length / 1000.0 * unit_w, 2)
    w_group = round(length / 1000.0 * unit_w * count, 1)
    bl = _pset(f, bar, "Tekla Reinforcement - Bending List")
    _set_prop(f, bl, "Size", f.create_entity("IfcIdentifier", str(size)))
    _set_prop(f, bl, "Number of bars in group", f.create_entity("IfcInteger", count))
    _set_prop(f, bl, "Weight", f.create_entity("IfcMassMeasure", w_each))
    _set_prop(f, bl, "Weight total in group", f.create_entity("IfcMassMeasure", w_group))
    gen = _pset(f, bar, "Tekla Reinforcement - General")
    _set_prop(f, gen, "Spacing exact", f.create_entity("IfcLabel", f"{count - 1}*{round(lay.spacing):d}"))
    _set_prop(f, gen, "Spacing target", f.create_entity("IfcLengthMeasure", round(lay.spacing, 1)))
    return {"guid": bar.GlobalId, "weight_each": w_each, "weight_group": w_group,
            "old_weight_group": None}


# --------------------------------------------------------------------------- #
# 실행 함수 (CLI · 웹 화면 공용)
# --------------------------------------------------------------------------- #
def modify(f, size=19, count=5, cover=40.0, max_aggregate=25.0, position="BOTH", log=print,
           spacing: float | None = None) -> dict:
    """열린 IFC(f)를 제자리에서 수정하고 변경 내역(dict)을 반환한다."""
    if size not in KS_D3504:
        raise ValueError(f"지원 호칭: {sorted(KS_D3504)}")
    if count < 1:
        raise ValueError("개수는 1 이상이어야 합니다.")
    beam, st, mains = analyze(f)
    m0 = next(b for b in f.by_type("IfcReinforcingBar") if b.GlobalId == mains[0].guid)
    d_hat = _bar_frame(m0)[2]

    log("=" * 70)
    log(f"[분석] 보 {beam.name} {beam.width:.0f}x{beam.height:.0f}  "
        f"폭 {beam.x_min:.1f}~{beam.x_max:.1f}, 높이 {beam.z_min:.1f}~{beam.z_max:.1f}")
    log(f"[분석] 늑근 D{round(st.diameter)} (Ø{st.diameter}), 굽힘 내반경 {st.bend_radius_inner:.2f} mm")
    for mi in mains:
        log(f"[분석] {mi.position:6s} 주근 D{mi.size} x {mi.count}  L={mi.length:.0f}  "
            f"X={mi.centers_x}  Z={mi.center_z}  간격 {mi.spacing:.2f}")

    # 원본 재현 검증: 같은 규칙으로 원본 배근을 계산해 모델 좌표와 일치하는지 확인
    log("-" * 70)
    report = {"beam": asdict(beam), "stirrup": asdict(st), "before": [asdict(m) for m in mains],
              "after": [], "warnings": [], "reproduction": []}
    for mi in mains:
        ref = compute_layout(beam, st, mi.position, mi.size, mi.count, cover, max_aggregate)
        dx = max(abs(x - y) for x, y in zip(ref.centers_x, mi.centers_x))
        dz = abs(ref.center_z - mi.center_z)
        good = dx < TOL and dz < TOL
        report["reproduction"].append({"position": mi.position, "dx": dx, "dz": dz, "ok": good})
        log(f"[재현검증] {mi.position:6s} 계산 vs 모델  ΔX max {dx:.3f}  ΔZ {dz:.3f}  → {'OK' if good else 'MISMATCH'}")
    if not all(r["ok"] for r in report["reproduction"]):
        log("  ! 배치 규칙이 원본과 다릅니다. 피복두께 등 입력값을 확인하세요.")

    # 신규 배근
    log("-" * 70)
    total_delta = 0.0
    for mi in mains:
        if position != "BOTH" and mi.position != position:
            continue
        lay = compute_layout(beam, st, mi.position, size, count, cover, max_aggregate, spacing)
        warns = check_layout(lay, max_aggregate)
        report["warnings"] += warns
        for w in warns:
            log("  ! " + w)
        bar = next(b for b in f.by_type("IfcReinforcingBar") if b.GlobalId == mi.guid)
        old_w = uel.get_psets(bar)["Tekla Reinforcement - Bending List"]["Weight total in group"]
        res = apply_layout(f, bar, lay, d_hat)
        res["old_weight_group"] = old_w
        total_delta += res["weight_group"] - old_w
        log(f"[변경] {lay.position:6s} D{mi.size}x{mi.count} → D{size}x{count}  "
            f"X={[round(x, 2) for x in lay.centers_x]}  Z={lay.center_z:.2f}")
        log(f"        중심간격 {lay.spacing:.2f}  순간격 {lay.clear_spacing:.2f}  "
            f"중량 {old_w} → {res['weight_group']} kg")
        report["after"].append({**asdict(lay), **res})

    # 부재(Assembly) 철근 총중량
    for asm in f.by_type("IfcElementAssembly"):
        ps = _pset(f, asm, "Tekla Assembly")
        if ps:
            cur = uel.get_psets(asm)["Tekla Assembly"].get("Cast unit rebar weight")
            if cur is not None:
                new = round(cur + total_delta, 1)
                _set_prop(f, ps, "Cast unit rebar weight", f.create_entity("IfcMassMeasure", new))
                log(f"[변경] Assembly 철근중량 {cur} → {new} kg")
                report["assembly_rebar_weight"] = {"before": cur, "after": new}

    try:
        f.header.file_name.preprocessor_version = f"IfcOpenShell {ifcopenshell.version} / modify_rebar.py"
    except Exception:
        pass
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description="IFC 보 주근 직경/개수 변경 및 등간격 재배치")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--size", type=int, default=19, help="주근 호칭 (KS D 3504, 예: 19 → D19)")
    ap.add_argument("--count", type=int, default=5, help="상·하부 각 주근 개수")
    ap.add_argument("--cover", type=float, default=40.0, help="피복두께 mm (구조일반사항)")
    ap.add_argument("--max-aggregate", type=float, default=25.0, help="굵은골재 최대치수 mm (순간격 검토)")
    ap.add_argument("--position", choices=["TOP", "BOTTOM", "BOTH"], default="BOTH")
    ap.add_argument("--spacing", type=float, default=None,
                    help="주근 중심간격 mm 직접 지정 (생략 시 유효폭 자동 등분)")
    ap.add_argument("--report", help="변경 내역 JSON 저장 경로")
    a = ap.parse_args(argv)
    if a.size not in KS_D3504:
        ap.error(f"지원 호칭: {sorted(KS_D3504)}")

    f = ifcopenshell.open(a.input)
    report = modify(f, a.size, a.count, a.cover, a.max_aggregate, a.position, spacing=a.spacing)
    report.update(input=a.input, output=a.output)
    f.write(a.output)
    print("=" * 70)
    print(f"[저장] {a.output}")
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fp:
            json.dump(report, fp, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
