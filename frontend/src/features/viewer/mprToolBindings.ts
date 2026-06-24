import type { ToolName } from "@/store/viewerStore";

/** Maps a toolbar tool id to the Cornerstone3D tool class name. */
export const MPR_TOOL_NAME: Record<ToolName, string> = {
  WindowLevel: "WindowLevel",
  Pan: "Pan",
  Zoom: "Zoom",
  StackScroll: "StackScroll",
  Rotate: "PlanarRotate",
  Crosshairs: "Crosshairs",
  Length: "Length",
  Angle: "Angle",
  RectangleROI: "RectangleROI",
  EllipticalROI: "EllipticalROI",
  Bidirectional: "Bidirectional",
  Probe: "Probe",
  ArrowAnnotate: "ArrowAnnotate",
};

export const MPR_PRIMARY_TOOLS = Object.values(MPR_TOOL_NAME);

const WHEEL_TOOL = "StackScrollMouseWheel";

/**
 * Reset and apply mouse bindings for the MPR tool group.
 *
 * Cornerstone merges bindings across setToolActive calls and setToolPassive only
 * strips primary bindings — so we disable every tool first, then activate cleanly.
 */
export function applyMprToolBindings(
  csTools: { Enums: { MouseBindings: Record<string, number> } },
  tg: {
    setToolDisabled: (name: string) => void;
    setToolEnabled: (name: string) => void;
    setToolActive: (name: string, opts?: { bindings?: { mouseButton: number }[] }) => void;
  },
  primaryToolName: string,
  toolNames: string[] = MPR_PRIMARY_TOOLS,
) {
  const { MouseBindings } = csTools.Enums;
  const all = [...toolNames, WHEEL_TOOL];

  all.forEach((name) => {
    try {
      tg.setToolDisabled(name);
    } catch {
      /* noop */
    }
  });
  all.forEach((name) => {
    try {
      tg.setToolEnabled(name);
    } catch {
      /* noop */
    }
  });

  const primary = toolNames.includes(primaryToolName) ? primaryToolName : "WindowLevel";

  tg.setToolActive(primary, {
    bindings: [{ mouseButton: MouseBindings.Primary }],
  });

  const zoomBindings =
    primary === "Zoom"
      ? [
          { mouseButton: MouseBindings.Primary },
          { mouseButton: MouseBindings.Secondary },
        ]
      : [{ mouseButton: MouseBindings.Secondary }];
  tg.setToolActive("Zoom", { bindings: zoomBindings });

  const panBindings =
    primary === "Pan"
      ? [
          { mouseButton: MouseBindings.Primary },
          { mouseButton: MouseBindings.Auxiliary },
        ]
      : [{ mouseButton: MouseBindings.Auxiliary }];
  tg.setToolActive("Pan", { bindings: panBindings });

  tg.setToolActive(WHEEL_TOOL);
}

/** Zoom a Cornerstone viewport in or out (works for stack + orthographic volume). */
export function zoomViewport(vp: {
  getZoom?: () => number;
  setZoom?: (value: number, store?: boolean) => void;
  getCamera?: () => { parallelScale?: number; [key: string]: unknown };
  setCamera?: (camera: Record<string, unknown>, store?: boolean) => void;
  render?: () => void;
}, direction: "in" | "out") {
  const zoomMul = direction === "in" ? 1.25 : 0.8;
  const scaleMul = direction === "in" ? 0.8 : 1.25;

  try {
    if (typeof vp.getZoom === "function" && typeof vp.setZoom === "function") {
      const current = vp.getZoom();
      if (Number.isFinite(current) && current > 0) {
        vp.setZoom(Math.min(Math.max(current * zoomMul, 0.05), 40));
        vp.render?.();
        return;
      }
    }
  } catch {
    /* fall through */
  }

  const cam = vp.getCamera?.();
  if (cam?.parallelScale != null && typeof vp.setCamera === "function") {
    const next = cam.parallelScale * scaleMul;
    vp.setCamera({ ...cam, parallelScale: Math.min(Math.max(next, 0.05), 1e6) });
    vp.render?.();
  }
}
