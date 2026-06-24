"""DICOM RT Structure Set (RTSTRUCT) parsing.

Extracts contoured ROIs (organs, targets) from an RTSTRUCT file and turns them into
structured segmentation results: name, type, display color, computed volume, and a
normalized bounding box mapped onto the reference CT geometry so the viewer can locate it.

This is the bridge that lets a real RT planning study (e.g. the LtBreast demo) produce
genuine segmentation + finding output instead of the synthetic stub.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pydicom

from app.core.logging import get_logger

logger = get_logger(__name__)

# Keyword -> structure type classification.
_TARGET_KEYS = ("ctv", "ptv", "gtv", "itv", "tumor", "tumour", "lesion", "target", "boost")
_ORGAN_KEYS = (
    "lung", "heart", "liver", "kidney", "breast", "eso", "cord", "skin", "brain",
    "bladder", "rectum", "bowel", "stomach", "spleen", "parotid", "chiasm", "optic",
    "lens", "eye", "trachea", "bronchus", "femur", "humerus",
)
_BONE_KEYS = ("bone", "rib", "sternum", "vertebra", "femur", "pelvis")
_SUPPORT_KEYS = ("baseplate", "couch", "ring", "plan ", "marker", "ref", "iso")


@dataclass
class ContourPolygon:
    """One closed contour on a single axial slice (z in patient mm)."""

    z_mm: float
    points: list[list[float]]  # normalized [x, y] in 0..1 (column, row)


@dataclass
class RoiResult:
    label: str
    structure_type: str  # organ | tumor | bone | other
    color: str  # hex
    volume_cc: float | None
    num_contours: int
    bbox: dict = field(default_factory=dict)
    is_target: bool = False
    contours: list[ContourPolygon] = field(default_factory=list)


@dataclass
class ReferenceGeometry:
    """Axial CT geometry used to map patient mm coords -> normalized image coords."""

    origin_x: float
    origin_y: float
    spacing_col: float
    spacing_row: float
    rows: int
    cols: int


def is_rtstruct(data: bytes) -> bool:
    try:
        ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
        return str(getattr(ds, "Modality", "")).upper() == "RTSTRUCT"
    except Exception:  # noqa: BLE001
        return False


def reference_geometry_from_image(data: bytes) -> ReferenceGeometry | None:
    try:
        ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
        ipp = [float(v) for v in getattr(ds, "ImagePositionPatient", [0, 0, 0])]
        ps = [float(v) for v in getattr(ds, "PixelSpacing", [1, 1])]
        return ReferenceGeometry(
            origin_x=ipp[0],
            origin_y=ipp[1],
            spacing_row=ps[0],
            spacing_col=ps[1],
            rows=int(getattr(ds, "Rows", 512)),
            cols=int(getattr(ds, "Columns", 512)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read reference geometry: %s", exc)
        return None


def _classify(name: str) -> tuple[str, bool]:
    low = name.lower()
    if any(k in low for k in _TARGET_KEYS):
        return "tumor", True
    if any(k in low for k in _BONE_KEYS):
        return "bone", False
    if any(k in low for k in _SUPPORT_KEYS):
        return "other", False
    if any(k in low for k in _ORGAN_KEYS):
        return "organ", False
    return "organ", False


def _polygon_area(xy: list[tuple[float, float]]) -> float:
    """Shoelace area in mm^2."""
    n = len(xy)
    if n < 3:
        return 0.0
    a = 0.0
    for i in range(n):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _color_hex(rgb) -> str:
    try:
        r, g, b = (int(v) for v in rgb[:3])
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:  # noqa: BLE001
        return "#38bdf8"


def parse_rtstruct(data: bytes, geometry: ReferenceGeometry | None = None) -> list[RoiResult]:
    ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)

    # Map ROINumber -> name.
    names: dict[int, str] = {}
    for roi in getattr(ds, "StructureSetROISequence", []):
        names[int(roi.ROINumber)] = str(getattr(roi, "ROIName", f"ROI {roi.ROINumber}"))

    # Estimate slice thickness from the spread of contour z positions.
    thickness = _estimate_thickness(ds)

    results: list[RoiResult] = []
    for roi_contour in getattr(ds, "ROIContourSequence", []):
        roi_number = int(getattr(roi_contour, "ReferencedROINumber", -1))
        name = names.get(roi_number, f"ROI {roi_number}")
        color = _color_hex(getattr(roi_contour, "ROIDisplayColor", [56, 189, 248]))

        contours = getattr(roi_contour, "ContourSequence", []) or []
        total_area = 0.0
        all_x: list[float] = []
        all_y: list[float] = []
        contour_polys: list[ContourPolygon] = []
        for c in contours:
            pts = [float(v) for v in getattr(c, "ContourData", [])]
            xy = [(pts[i], pts[i + 1]) for i in range(0, len(pts), 3)]
            if not xy:
                continue
            total_area += _polygon_area(xy)
            all_x.extend(p[0] for p in xy)
            all_y.extend(p[1] for p in xy)
            z_mm = round(float(pts[2]), 2) if len(pts) >= 3 else 0.0
            norm_pts = _normalize_xy(xy, geometry)
            if len(norm_pts) >= 3:
                contour_polys.append(ContourPolygon(z_mm=z_mm, points=norm_pts))

        volume_cc = round(total_area * thickness / 1000.0, 1) if total_area else None
        stype, is_target = _classify(name)
        bbox = _bbox(all_x, all_y, geometry)

        results.append(
            RoiResult(
                label=name,
                structure_type=stype,
                color=color,
                volume_cc=volume_cc,
                num_contours=len(contours),
                bbox=bbox,
                is_target=is_target,
                contours=contour_polys,
            )
        )

    return results


def _estimate_thickness(ds) -> float:
    zs: set[float] = set()
    for roi_contour in getattr(ds, "ROIContourSequence", []):
        for c in getattr(roi_contour, "ContourSequence", []) or []:
            data = getattr(c, "ContourData", [])
            if len(data) >= 3:
                zs.add(round(float(data[2]), 2))
    zlist = sorted(zs)
    diffs = [round(b - a, 2) for a, b in zip(zlist, zlist[1:], strict=False) if 0 < (b - a) < 20]
    if diffs:
        diffs.sort()
        return diffs[len(diffs) // 2]  # median spacing
    return 3.0


def _normalize_xy(
    xy: list[tuple[float, float]], geo: ReferenceGeometry | None
) -> list[list[float]]:
    """Map patient (x,y) mm coords to normalized axial image coords."""
    if not geo or not geo.spacing_col or not geo.spacing_row:
        return []
    out: list[list[float]] = []
    for x, y in xy:
        col = (x - geo.origin_x) / geo.spacing_col / max(geo.cols, 1)
        row = (y - geo.origin_y) / geo.spacing_row / max(geo.rows, 1)
        out.append([round(max(0.0, min(1.0, col)), 4), round(max(0.0, min(1.0, row)), 4)])
    return out


def _bbox(xs: list[float], ys: list[float], geo: ReferenceGeometry | None) -> dict:
    if not xs or not ys:
        return {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if geo and geo.spacing_col and geo.spacing_row:
        def col(x: float) -> float:
            return (x - geo.origin_x) / geo.spacing_col / max(geo.cols, 1)

        def row(y: float) -> float:
            return (y - geo.origin_y) / geo.spacing_row / max(geo.rows, 1)

        x0, x1 = sorted((col(min_x), col(max_x)))
        y0, y1 = sorted((row(min_y), row(max_y)))
        x0, y0 = max(0.0, x0), max(0.0, y0)
        x1, y1 = min(1.0, x1), min(1.0, y1)
        return {
            "x": round(x0, 4),
            "y": round(y0, 4),
            "w": round(max(x1 - x0, 0.01), 4),
            "h": round(max(y1 - y0, 0.01), 4),
            "slice": 0.5,
        }
    # No geometry: centered placeholder.
    return {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}
