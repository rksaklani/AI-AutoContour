import { useCallback, useEffect, useState } from "react";

import { EmptyState, Panel } from "@/components/ui";

interface MeasurementRow {
  uid: string;
  tool: string;
  value: string;
}

const MEASURE_TOOLS = new Set([
  "Length",
  "Angle",
  "Bidirectional",
  "RectangleROI",
  "EllipticalROI",
  "Probe",
  "ArrowAnnotate",
]);

const TOOL_LABEL: Record<string, string> = {
  Length: "Length",
  Angle: "Angle",
  Bidirectional: "Bidirectional",
  RectangleROI: "Rect ROI",
  EllipticalROI: "Ellipse ROI",
  Probe: "Probe",
  ArrowAnnotate: "Text",
};

/**
 * Lists the measurements/annotations the user has drawn with the Cornerstone3D
 * tools, with their computed values, and lets them delete individually or clear
 * all. Reads live annotation state and refreshes on annotation events.
 */
export function MeasurementsPanel() {
  const [rows, setRows] = useState<MeasurementRow[]>([]);

  const refresh = useCallback(async () => {
    try {
      const csTools = (await import("@cornerstonejs/tools")) as any;
      const all = (csTools.annotation?.state?.getAllAnnotations?.() ?? []) as any[];
      const measured = all.filter((a) => MEASURE_TOOLS.has(a?.metadata?.toolName));
      setRows(
        measured.map((a) => ({
          uid: a.annotationUID,
          tool: a.metadata.toolName,
          value: summarize(a),
        })),
      );
    } catch {
      setRows([]);
    }
  }, []);

  useEffect(() => {
    let target: any = null;
    let events: string[] = [];
    const handler = () => refresh();
    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const csTools = (await import("@cornerstonejs/tools")) as any;
        target = cs.eventTarget;
        const E = csTools.Enums.Events;
        events = [
          E.ANNOTATION_ADDED,
          E.ANNOTATION_MODIFIED,
          E.ANNOTATION_REMOVED,
          E.ANNOTATION_COMPLETED,
        ].filter(Boolean);
        events.forEach((e) => target.addEventListener(e, handler));
        refresh();
      } catch {
        /* noop */
      }
    })();
    return () => {
      try {
        events.forEach((e) => target?.removeEventListener(e, handler));
      } catch {
        /* noop */
      }
    };
  }, [refresh]);

  async function removeOne(uid: string) {
    try {
      const csTools = (await import("@cornerstonejs/tools")) as any;
      const cs = (await import("@cornerstonejs/core")) as any;
      csTools.annotation.state.removeAnnotation(uid);
      cs.getRenderingEngines?.().forEach((e: any) => e.render());
    } catch {
      /* noop */
    }
    refresh();
  }

  async function clearAll() {
    try {
      const csTools = (await import("@cornerstonejs/tools")) as any;
      const cs = (await import("@cornerstonejs/core")) as any;
      rows.forEach((r) => {
        try {
          csTools.annotation.state.removeAnnotation(r.uid);
        } catch {
          /* noop */
        }
      });
      cs.getRenderingEngines?.().forEach((e: any) => e.render());
    } catch {
      /* noop */
    }
    refresh();
  }

  return (
    <Panel
      title={`Measurements (${rows.length})`}
      className="shrink-0"
      actions={
        rows.length > 0 ? (
          <button onClick={clearAll} className="text-xs text-slate-400 hover:text-red-400">
            Clear all
          </button>
        ) : undefined
      }
    >
      {rows.length === 0 ? (
        <EmptyState title="No measurements" hint="Use Length, Angle, ROI, or Probe tools." />
      ) : (
        <ul className="max-h-44 divide-y divide-surface-700 overflow-auto">
          {rows.map((r) => (
            <li key={r.uid} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
              <span className="text-slate-500">{TOOL_LABEL[r.tool] ?? r.tool}</span>
              <span className="flex-1 truncate text-right font-medium text-slate-200">{r.value}</span>
              <button
                onClick={() => removeOne(r.uid)}
                className="text-slate-500 hover:text-red-400"
                title="Delete"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function fmt(v: number | undefined | null, unit = "", digits = 1): string | null {
  if (v == null || Number.isNaN(v)) return null;
  return `${v.toFixed(digits)}${unit}`;
}

function summarize(a: any): string {
  const tool = a?.metadata?.toolName;
  if (tool === "ArrowAnnotate") return a?.data?.text || "(text)";
  const statsMap = a?.data?.cachedStats;
  const stats = statsMap ? (Object.values(statsMap)[0] as any) : null;
  if (!stats) return "—";
  switch (tool) {
    case "Length":
      return fmt(stats.length, " mm") ?? "—";
    case "Angle":
      return fmt(stats.angle, "°") ?? "—";
    case "Bidirectional":
      return [fmt(stats.length, " mm"), fmt(stats.width, " mm")].filter(Boolean).join(" × ") || "—";
    case "RectangleROI":
    case "EllipticalROI": {
      const parts = [fmt(stats.area, " mm²", 0), fmt(stats.mean, "", 0) && `μ ${fmt(stats.mean, "", 0)}`];
      return parts.filter(Boolean).join("  ") || "—";
    }
    case "Probe":
      return fmt(stats.value, "", 0) ?? "—";
    default:
      return "—";
  }
}
