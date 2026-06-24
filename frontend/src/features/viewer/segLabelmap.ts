/**
 * AI labelmap segmentation for the MPR + 3D viewports.
 *
 * The backend overlay payload carries per-slice contour polygons (RTSTRUCT /
 * VISTA3D expert masks) or, as a fallback, a single bounding box on a
 * representative slice. The SVG `SegmentationOverlay` only paints those on the
 * axial plane. To show the same regions in coronal, sagittal AND the 3D render
 * we rasterize them into a real Cornerstone3D labelmap volume (one segment per
 * ROI) that the renderer reformats into every viewport for free.
 *
 * polyseg WASM is stubbed out in this build, so contour->labelmap conversion is
 * done here by direct voxel scan-fill rather than Cornerstone's converter.
 */
import type { RoiOverlay, StudyOverlay } from "@/types";

/** In-plane / through-plane flips, exposed so display mirroring is a 1-line fix. */
const FLIP_X = false;
const FLIP_Y = false;

export interface LabelmapSegment {
  /** 1-based segment index written into the labelmap voxels. */
  index: number;
  /** Stable id used for per-ROI opacity / visibility toggles. */
  segId: string;
  label: string;
  color: [number, number, number];
}

export interface BuiltLabelmap {
  segmentationId: string;
  segVolumeId: string;
  segments: LabelmapSegment[];
}

/** Parse a CSS color (`rgb(...)`, `#rgb`, `#rrggbb`) into an [r,g,b] 0-255 triple. */
function parseColor(css: string | undefined): [number, number, number] {
  if (!css) return [255, 96, 96];
  const rgb = css.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
  const hex = css.trim().replace(/^#/, "");
  if (hex.length === 3) {
    return [
      parseInt(hex[0] + hex[0], 16),
      parseInt(hex[1] + hex[1], 16),
      parseInt(hex[2] + hex[2], 16),
    ];
  }
  if (hex.length === 6) {
    return [
      parseInt(hex.slice(0, 2), 16),
      parseInt(hex.slice(2, 4), 16),
      parseInt(hex.slice(4, 6), 16),
    ];
  }
  return [255, 96, 96];
}

/** Index of the slice whose z position is closest to `zMm`. */
function nearestSlice(sliceZ: number[], zMm: number): number {
  let best = 0;
  let bestDist = Infinity;
  for (let k = 0; k < sliceZ.length; k++) {
    const d = Math.abs(sliceZ[k] - zMm);
    if (d < bestDist) {
      bestDist = d;
      best = k;
    }
  }
  return best;
}

function toPixel(nx: number, ny: number, cols: number, rows: number): [number, number] {
  let px = nx * (cols - 1);
  let py = ny * (rows - 1);
  if (FLIP_X) px = cols - 1 - px;
  if (FLIP_Y) py = rows - 1 - py;
  return [px, py];
}

/** Even-odd scan-fill of a polygon (pixel coords) into slice `k` of the labelmap. */
function fillPolygon(
  data: Uint8Array | Uint16Array | Float32Array,
  cols: number,
  rows: number,
  k: number,
  pts: Array<[number, number]>,
  seg: number,
) {
  if (pts.length < 3) return;
  const base = k * cols * rows;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const [, py] of pts) {
    if (py < minY) minY = py;
    if (py > maxY) maxY = py;
  }
  const y0 = Math.max(0, Math.floor(minY));
  const y1 = Math.min(rows - 1, Math.ceil(maxY));
  for (let yy = y0; yy <= y1; yy++) {
    const yc = yy + 0.5;
    const xs: number[] = [];
    for (let i = 0; i < pts.length; i++) {
      const [x1, py1] = pts[i];
      const [x2, py2] = pts[(i + 1) % pts.length];
      if ((py1 <= yc && py2 > yc) || (py2 <= yc && py1 > yc)) {
        xs.push(x1 + ((yc - py1) / (py2 - py1)) * (x2 - x1));
      }
    }
    xs.sort((a, b) => a - b);
    for (let s = 0; s + 1 < xs.length; s += 2) {
      const xStart = Math.max(0, Math.ceil(xs[s] - 0.5));
      const xEnd = Math.min(cols - 1, Math.floor(xs[s + 1] - 0.5));
      const row = base + yy * cols;
      for (let xx = xStart; xx <= xEnd; xx++) data[row + xx] = seg;
    }
  }
}

function fillBox(
  data: Uint8Array | Uint16Array | Float32Array,
  cols: number,
  rows: number,
  k: number,
  bbox: Record<string, number>,
  seg: number,
) {
  const [px0, py0] = toPixel(bbox.x ?? 0, bbox.y ?? 0, cols, rows);
  const [px1, py1] = toPixel(
    (bbox.x ?? 0) + (bbox.w ?? 0.1),
    (bbox.y ?? 0) + (bbox.h ?? 0.1),
    cols,
    rows,
  );
  const x0 = Math.max(0, Math.floor(Math.min(px0, px1)));
  const x1 = Math.min(cols - 1, Math.ceil(Math.max(px0, px1)));
  const y0 = Math.max(0, Math.floor(Math.min(py0, py1)));
  const y1 = Math.min(rows - 1, Math.ceil(Math.max(py0, py1)));
  const base = k * cols * rows;
  for (let yy = y0; yy <= y1; yy++) {
    const row = base + yy * cols;
    for (let xx = x0; xx <= x1; xx++) data[row + xx] = seg;
  }
}

/** Rasterize every ROI in the overlay into the labelmap scalar data. */
function rasterize(
  data: Uint8Array | Uint16Array | Float32Array,
  dims: [number, number, number],
  overlay: StudyOverlay,
  segments: Array<{ roi: RoiOverlay; index: number }>,
) {
  const [cols, rows, slices] = dims;
  const sliceZ = overlay.slice_z_mm ?? [];
  data.fill(0);
  for (const { roi, index } of segments) {
    if (roi.contours && roi.contours.length > 0) {
      for (const c of roi.contours) {
        const k =
          sliceZ.length > 0
            ? Math.min(slices - 1, nearestSlice(sliceZ, c.z_mm))
            : Math.floor(slices / 2);
        const pts = c.points.map(
          (p) => toPixel(p[0], p[1], cols, rows) as [number, number],
        );
        fillPolygon(data, cols, rows, k, pts, index);
      }
    } else if (roi.bbox && Object.keys(roi.bbox).length > 0) {
      const norm = roi.bbox.slice ?? 0.5;
      const k = Math.max(0, Math.min(slices - 1, Math.round(norm * (slices - 1))));
      fillBox(data, cols, rows, k, roi.bbox, index);
    }
  }
}

function scalarArray(volume: any): Uint8Array | Uint16Array | Float32Array | null {
  try {
    const arr = volume.getScalarData?.();
    if (arr) return arr;
  } catch {
    /* fall through */
  }
  try {
    const arr = volume.voxelManager?.getCompleteScalarDataArray?.();
    if (arr) return arr;
  } catch {
    /* noop */
  }
  return null;
}

/**
 * Create (or rebuild) the derived labelmap volume for `overlay`, rasterize all
 * ROIs into it, and register it as a global segmentation. Returns null when the
 * overlay has nothing paintable.
 */
export async function buildLabelmap(
  cs: any,
  csTools: any,
  opts: { referenceVolumeId: string; segmentationId: string; segVolumeId: string; overlay: StudyOverlay },
): Promise<BuiltLabelmap | null> {
  const { referenceVolumeId, segmentationId, segVolumeId, overlay } = opts;
  const rois = (overlay.rois ?? []).filter(
    (r) => (r.contours && r.contours.length > 0) || (r.bbox && Object.keys(r.bbox).length > 0),
  );
  if (rois.length === 0) return null;

  const segments: LabelmapSegment[] = rois.map((roi, i) => ({
    index: i + 1,
    segId: roi.segmentation_id ?? roi.label ?? `roi-${i}`,
    label: roi.label ?? `Region ${i + 1}`,
    color: parseColor(roi.color),
  }));

  // Defensive: purge any stale state/volume left under these ids.
  try {
    csTools.segmentation.state.removeSegmentation?.(segmentationId);
  } catch {
    /* noop */
  }
  try {
    cs.cache.removeVolumeLoadObject?.(segVolumeId);
  } catch {
    /* noop */
  }

  const segVolume = await cs.volumeLoader.createAndCacheDerivedSegmentationVolume(
    referenceVolumeId,
    { volumeId: segVolumeId },
  );
  const data = scalarArray(segVolume);
  if (!data) return null;

  const dims = segVolume.dimensions as [number, number, number];
  rasterize(data, dims, overlay, segments.map((s, i) => ({ roi: rois[i], index: s.index })));

  // Persist mutated voxels if the volume is backed by a voxel manager copy.
  try {
    segVolume.voxelManager?.setCompleteScalarDataArray?.(data);
  } catch {
    /* noop */
  }
  try {
    segVolume.modified?.();
  } catch {
    /* noop */
  }

  const { SegmentationRepresentations } = csTools.Enums;
  csTools.segmentation.addSegmentations([
    {
      segmentationId,
      representation: {
        type: SegmentationRepresentations.Labelmap,
        data: { volumeId: segVolumeId },
      },
    },
  ]);

  try {
    csTools.segmentation.triggerSegmentationEvents.triggerSegmentationDataModified(segmentationId);
  } catch {
    /* noop */
  }

  return { segmentationId, segVolumeId, segments };
}

/**
 * Attach a labelmap representation of `segmentationId` to a tool group's
 * viewports (works for both the MPR engine and the 3D engine). Returns the
 * representation UID, or null on failure.
 */
export async function addLabelmapToToolGroup(
  csTools: any,
  toolGroupId: string,
  segmentationId: string,
): Promise<string | null> {
  try {
    const tg = csTools.ToolGroupManager.getToolGroup(toolGroupId);
    if (tg) {
      try {
        tg.addTool(csTools.SegmentationDisplayTool.toolName);
      } catch {
        /* already added */
      }
      try {
        tg.setToolEnabled(csTools.SegmentationDisplayTool.toolName);
      } catch {
        /* noop */
      }
    }
    const { SegmentationRepresentations } = csTools.Enums;
    const uids = await csTools.segmentation.addSegmentationRepresentations(toolGroupId, [
      { segmentationId, type: SegmentationRepresentations.Labelmap },
    ]);
    return uids?.[0] ?? null;
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("addLabelmapToToolGroup failed:", err);
    return null;
  }
}

/** Apply per-segment color, the global mask toggle, individual hides and opacity. */
export function applyLabelmapAppearance(
  csTools: any,
  toolGroupId: string,
  repUID: string,
  segments: LabelmapSegment[],
  opts: {
    showSegmentations: boolean;
    segOpacity: Record<string, number>;
    hiddenSegIds: Record<string, boolean>;
  },
) {
  const { color, visibility } = csTools.segmentation.config;
  const opacities: number[] = [];
  for (const seg of segments) {
    try {
      color.setColorForSegmentIndex(toolGroupId, repUID, seg.index, [...seg.color, 255]);
    } catch {
      /* noop */
    }
    const hidden = Boolean(opts.hiddenSegIds[seg.segId]);
    try {
      visibility.setSegmentVisibility(toolGroupId, repUID, seg.index, !hidden);
    } catch {
      /* noop */
    }
    const o = opts.segOpacity[seg.segId];
    if (typeof o === "number") opacities.push(o);
  }
  try {
    visibility.setSegmentationVisibility(toolGroupId, repUID, opts.showSegmentations);
  } catch {
    /* noop */
  }
  const fillAlpha = opacities.length
    ? opacities.reduce((a, b) => a + b, 0) / opacities.length
    : 0.5;
  try {
    csTools.segmentation.config.setSegmentationRepresentationSpecificConfig(
      toolGroupId,
      repUID,
      { LABELMAP: { fillAlpha, renderOutline: true, outlineWidthActive: 2 } },
    );
  } catch {
    /* noop */
  }
}

/**
 * Fully dispose a labelmap: drop its tool-group representation, remove the
 * global segmentation state, and purge the derived volume (and its GPU texture)
 * from the cache. Purging the volume is essential — a cached seg volume keeps a
 * WebGL texture bound to the old rendering context, which corrupts rendering
 * after the engine is destroyed/recreated on a re-analyze.
 */
export function teardownLabelmap(
  cs: any,
  csTools: any,
  opts: { segmentationId: string; segVolumeId: string; toolGroupId: string; repUID?: string | null },
) {
  const { segmentationId, segVolumeId, toolGroupId, repUID } = opts;
  try {
    if (repUID) {
      csTools.segmentation.removeSegmentationsFromToolGroup(toolGroupId, [repUID]);
    } else {
      csTools.segmentation.removeSegmentationsFromToolGroup(toolGroupId);
    }
  } catch {
    /* noop */
  }
  try {
    csTools.segmentation.state.removeSegmentation?.(segmentationId);
  } catch {
    /* noop */
  }
  try {
    cs.cache.removeVolumeLoadObject?.(segVolumeId);
  } catch {
    /* noop */
  }
}
