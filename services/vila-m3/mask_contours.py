"""Extract viewer contours from VISTA3D / expert overlay images."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

# VISTA text: "The colors in this image describe #ff0000: liver, #00ff00: spleen."
_VISTA_LABELS = re.compile(
    r"(#[0-9a-fA-F]{3,8}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\))\s*:\s*([^,\.;]+)"
)


def parse_expert_labels(text: str) -> list[tuple[str, str]]:
    """Return (color_token, label) pairs parsed from expert model text."""
    out: list[tuple[str, str]] = []
    for match in _VISTA_LABELS.finditer(text or ""):
        color, label = match.group(1).strip(), match.group(2).strip()
        if label and label.lower() not in {"none", "background"}:
            out.append((color, label))
    return out


def _hex_to_rgb(token: str) -> tuple[int, int, int] | None:
    token = token.strip().lower()
    if token.startswith("rgb"):
        nums = re.findall(r"\d+", token)
        if len(nums) >= 3:
            return int(nums[0]), int(nums[1]), int(nums[2])
        return None
    if not token.startswith("#"):
        token = f"#{token}"
    h = token.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mask_for_color(arr: np.ndarray, rgb: tuple[int, int, int], tol: int = 28) -> np.ndarray:
    diff = np.abs(arr.astype(np.int16) - np.array(rgb, dtype=np.int16))
    return np.all(diff <= tol, axis=-1)


def bbox_contour_from_overlay(
    image_path: str,
    *,
    label: str,
    color: str,
    z_mm: float = 0.0,
) -> dict | None:
    """Build a normalized bounding-box contour for a colored region in an overlay PNG."""
    try:
        from PIL import Image
    except ImportError:
        return None

    path = Path(image_path)
    if not path.is_file():
        return None
    rgb = _hex_to_rgb(color)
    if rgb is None:
        return None

    img = np.array(Image.open(path).convert("RGB"))
    mask = _mask_for_color(img, rgb)
    if not mask.any():
        return None

    ys, xs = np.where(mask)
    h, w = mask.shape
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    if x1 <= x0 or y1 <= y0:
        return None

    nx0, ny0 = x0 / w, y0 / h
    nx1, ny1 = (x1 + 1) / w, (y1 + 1) / h
    points = [[nx0, ny0], [nx1, ny0], [nx1, ny1], [nx0, ny1]]
    return {
        "label": label,
        "color": color if color.startswith("#") else _rgb_to_hex(rgb),
        "contours": [{"z_mm": z_mm, "points": points}],
        "bbox": {"x": nx0, "y": ny0, "w": nx1 - nx0, "h": ny1 - ny0, "slice": 0.5},
    }


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def segmentations_from_expert(
    expert_text: str,
    overlay_paths: list[str],
    *,
    z_mm: float = 0.0,
) -> list[dict]:
    """Parse expert output into Lumira-style segmentation dicts with contours."""
    labels = parse_expert_labels(expert_text)
    if not labels and overlay_paths:
        labels = [("#38bdf8", "Expert segmentation")]

    segs: list[dict] = []
    overlay = overlay_paths[0] if overlay_paths else None
    for color, label in labels[:12]:
        item = None
        if overlay:
            item = bbox_contour_from_overlay(overlay, label=label, color=color, z_mm=z_mm)
        if item is None:
            item = {
                "label": label,
                "color": color if color.startswith("#") else "#38bdf8",
                "contours": [],
                "bbox": {"x": 0.35, "y": 0.35, "w": 0.2, "h": 0.18, "slice": 0.5},
            }
        segs.append(item)
    return segs
