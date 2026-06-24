import type { RoiOverlay, StudyOverlay } from "@/types";

interface SegmentationOverlayProps {
  overlay: StudyOverlay | undefined;
  sliceIndex: number;
  sliceCount: number;
  currentZMm: number | null;
  show: boolean;
  segOpacity: Record<string, number>;
  hiddenSegIds: Record<string, boolean>;
}

/** SVG overlay for RTSTRUCT contours and stub mask bounding boxes on the axial plane. */
export function SegmentationOverlay({
  overlay,
  sliceIndex,
  sliceCount,
  currentZMm,
  show,
  segOpacity,
  hiddenSegIds,
}: SegmentationOverlayProps) {
  if (!show || !overlay || overlay.rois.length === 0) return null;

  const zTolerance = estimateZTolerance(overlay.slice_z_mm);
  const normSlice = sliceCount > 1 ? sliceIndex / (sliceCount - 1) : 0.5;

  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      {overlay.rois.map((roi) => (
        <RoiGraphic
          key={roi.segmentation_id ?? roi.label}
          roi={roi}
          sliceIndex={sliceIndex}
          sliceCount={sliceCount}
          normSlice={normSlice}
          currentZMm={currentZMm}
          zTolerance={zTolerance}
          opacity={segOpacity[roi.segmentation_id ?? ""] ?? 0.45}
          hidden={Boolean(roi.segmentation_id && hiddenSegIds[roi.segmentation_id])}
        />
      ))}
    </svg>
  );
}

function RoiGraphic({
  roi,
  sliceIndex,
  sliceCount,
  normSlice,
  currentZMm,
  zTolerance,
  opacity,
  hidden,
}: {
  roi: RoiOverlay;
  sliceIndex: number;
  sliceCount: number;
  normSlice: number;
  currentZMm: number | null;
  zTolerance: number;
  opacity: number;
  hidden: boolean;
}) {
  if (hidden) return null;

  const fillAlpha = Math.round(opacity * 100) / 100;
  const stroke = roi.color;

  if (roi.contours.length > 0) {
    const polys = roi.contours.filter((c) => {
      if (currentZMm != null) return Math.abs(c.z_mm - currentZMm) <= zTolerance;
      const target = roi.bbox?.slice ?? 0.5;
      return Math.abs(normSlice - target) < 0.08;
    });
    if (polys.length === 0) return null;
    return (
      <g>
        {polys.map((poly, i) => {
          const d =
            poly.points
              .map((p, j) => `${j === 0 ? "M" : "L"}${p[0] * 100} ${p[1] * 100}`)
              .join(" ") + " Z";
          return (
            <path
              key={`${roi.label}-${i}`}
              d={d}
              fill={stroke}
              fillOpacity={fillAlpha * 0.35}
              stroke={stroke}
              strokeWidth={0.35}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </g>
    );
  }

  const bbox = roi.bbox;
  if (!bbox || Object.keys(bbox).length === 0) return null;
  const targetSlice = bbox.slice ?? 0.5;
  const targetIndex = Math.round(targetSlice * Math.max(sliceCount - 1, 0));
  if (Math.abs(sliceIndex - targetIndex) > 1 && Math.abs(normSlice - targetSlice) > 0.06) {
    return null;
  }

  const x = (bbox.x ?? 0) * 100;
  const y = (bbox.y ?? 0) * 100;
  const w = (bbox.w ?? 0.1) * 100;
  const h = (bbox.h ?? 0.1) * 100;
  const area = (bbox.w ?? 0.1) * (bbox.h ?? 0.1);
  // Stub pipeline masks are solid-color PNGs stretched to organ-sized boxes — outline only.
  const outlineOnly = Boolean(roi.mask_url) || area > 0.12;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        fill={outlineOnly ? "none" : stroke}
        fillOpacity={outlineOnly ? 0 : fillAlpha * 0.15}
        stroke={stroke}
        strokeWidth={outlineOnly ? 0.5 : 0.35}
        strokeDasharray={outlineOnly ? "1.5 1" : undefined}
        vectorEffect="non-scaling-stroke"
      />
    </g>
  );
}

function estimateZTolerance(sliceZ: number[]): number {
  if (sliceZ.length < 2) return 2.5;
  const diffs: number[] = [];
  for (let i = 1; i < sliceZ.length; i++) {
    const d = Math.abs(sliceZ[i] - sliceZ[i - 1]);
    if (d > 0 && d < 20) diffs.push(d);
  }
  if (diffs.length === 0) return 2.5;
  diffs.sort((a, b) => a - b);
  return diffs[Math.floor(diffs.length / 2)] / 2 + 0.5;
}
