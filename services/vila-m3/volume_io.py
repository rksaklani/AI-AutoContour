"""Fetch a representative 2D slice from Lumira study instance URLs for VILA-M3."""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path
from urllib.request import urlopen

logger = logging.getLogger(__name__)

_IMAGE_MODALITIES = {"CT", "MR", "MRI", "PT", "PET", "US", "CR", "DX", "XR", "NM"}


def prepare_study_image(
    series_instances: list[dict],
    work_dir: str | None = None,
) -> tuple[str | None, str, float]:
    """Download middle DICOM instance and export PNG/JPEG for the VLM.

    Returns (image_path, modality, z_mm_patient).
    """
    instances = [
        i
        for i in series_instances
        if (i.get("modality") or "").upper() in _IMAGE_MODALITIES and i.get("url")
    ]
    if not instances:
        return None, "Unknown", 0.0

    instances.sort(key=lambda x: x.get("instance_number") or 0)
    mid = instances[len(instances) // 2]
    modality = (mid.get("modality") or "CT").upper()
    url = mid["url"]

    root = work_dir or tempfile.mkdtemp(prefix="lumira-vila-")
    Path(root).mkdir(parents=True, exist_ok=True)

    try:
        with urlopen(url, timeout=120) as resp:  # noqa: S310
            raw = resp.read()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to download instance %s: %s", url, exc)
        return None, modality, 0.0

    dcm_path = os.path.join(root, "slice.dcm")
    with open(dcm_path, "wb") as f:
        f.write(raw)

    z_mm = _slice_z_mm(dcm_path)
    mod = modality
    if mod in {"CR", "DX", "XR"}:
        out = _dicom_to_jpeg(dcm_path, os.path.join(root, "slice.jpg"))
        return (out, "chest x-ray", z_mm) if out else (None, modality, z_mm)

    out = _dicom_to_png(dcm_path, os.path.join(root, "slice.png"))
    return (out, "CT" if mod == "CT" else "MRI", z_mm) if out else (None, modality, z_mm)


def assemble_nifti_from_series(
    series_instances: list[dict],
    work_dir: str,
) -> str | None:
    """Stack CT/MR instances into a NIfTI volume for VISTA3D (when nibabel is available)."""
    instances = [
        i
        for i in series_instances
        if (i.get("modality") or "").upper() in {"CT", "MR", "MRI"} and i.get("url")
    ]
    if len(instances) < 2:
        return None
    try:
        import nibabel as nib
        import numpy as np
        import pydicom
    except ImportError:
        return None

    instances.sort(key=lambda x: x.get("instance_number") or 0)
    slices: list[np.ndarray] = []
    affine = None
    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)

    for idx, inst in enumerate(instances):
        try:
            with urlopen(inst["url"], timeout=120) as resp:  # noqa: S310
                raw = resp.read()
        except Exception:  # noqa: BLE001
            continue
        dcm_path = root / f"slice_{idx:04d}.dcm"
        dcm_path.write_bytes(raw)
        ds = pydicom.dcmread(str(dcm_path), force=True)
        slices.append(ds.pixel_array.astype(np.float32))
        if affine is None:
            affine = np.eye(4)
            ps = getattr(ds, "PixelSpacing", None)
            st = getattr(ds, "SliceThickness", None)
            ipp = getattr(ds, "ImagePositionPatient", None)
            if ps is not None and len(ps) >= 2:
                affine[0, 0] = float(ps[0])
                affine[1, 1] = float(ps[1])
            if st is not None:
                affine[2, 2] = float(st)
            if ipp is not None and len(ipp) >= 3:
                affine[0, 3] = float(ipp[0])
                affine[1, 3] = float(ipp[1])
                affine[2, 3] = float(ipp[2])

    if len(slices) < 2:
        return None
    vol = np.stack(slices, axis=-1)
    out = root / "volume.nii.gz"
    nib.save(nib.Nifti1Image(vol, affine), str(out))
    return str(out)


def _slice_z_mm(dcm_path: str) -> float:
    try:
        import pydicom

        ds = pydicom.dcmread(dcm_path, stop_before_pixels=True, force=True)
        ipp = getattr(ds, "ImagePositionPatient", None)
        if ipp is not None and len(ipp) >= 3:
            return round(float(ipp[2]), 2)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _dicom_to_png(dcm_path: str, out_path: str) -> str | None:
    try:
        import numpy as np
        import pydicom
        from PIL import Image
    except ImportError:
        logger.warning("pydicom/PIL not available for DICOM decode")
        return None

    try:
        ds = pydicom.dcmread(dcm_path, force=True)
        arr = ds.pixel_array.astype(np.float32)
        wc = float(getattr(ds, "WindowCenter", 40) or 40)
        ww = float(getattr(ds, "WindowWidth", 400) or 400)
        if isinstance(wc, pydicom.multival.MultiValue):
            wc = float(wc[0])
        if isinstance(ww, pydicom.multival.MultiValue):
            ww = float(ww[0])
        lo, hi = wc - ww / 2, wc + ww / 2
        arr = np.clip(arr, lo, hi)
        arr = ((arr - lo) / max(hi - lo, 1e-6) * 255.0).astype(np.uint8)
        Image.fromarray(arr).save(out_path)
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("DICOM→PNG failed: %s", exc)
        return None


def _dicom_to_jpeg(dcm_path: str, out_path: str) -> str | None:
    png_path = out_path.replace(".jpg", ".png")
    if not _dicom_to_png(dcm_path, png_path):
        return None
    try:
        from PIL import Image

        Image.open(png_path).convert("RGB").save(out_path, quality=92)
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("JPEG export failed: %s", exc)
        return png_path
