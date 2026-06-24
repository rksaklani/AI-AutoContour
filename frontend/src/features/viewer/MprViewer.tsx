import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

import { IconInfo } from "@/components/icons";
import { imageIdFromUrl, initCornerstone, VOLUME_LOADER_SCHEME } from "@/lib/cornerstoneInit";
import { SegmentationOverlay } from "@/features/viewer/SegmentationOverlay";
import {
  addLabelmapToToolGroup,
  applyLabelmapAppearance,
  buildLabelmap,
  teardownLabelmap,
  type BuiltLabelmap,
} from "@/features/viewer/segLabelmap";
import { applyMprToolBindings, MPR_PRIMARY_TOOLS, MPR_TOOL_NAME, zoomViewport } from "@/features/viewer/mprToolBindings";
import { VolumeViewport } from "@/features/viewer/VolumeViewport";
import { useViewerStore, type ToolName } from "@/store/viewerStore";
import type { Finding, StudyOverlay } from "@/types";

type View = "axial" | "coronal" | "sagittal";
const VIEWS: View[] = ["axial", "coronal", "sagittal"];

const REFERENCE_COLORS: Record<View, string> = {
  axial: "rgb(255, 96, 96)",
  coronal: "rgb(96, 220, 96)",
  sagittal: "rgb(96, 160, 255)",
};

/** Radiological orientation labels per plane (edge: anatomical direction). */
const ORIENTATION_LABELS: Record<View, { top: string; bottom: string; left: string; right: string }> = {
  axial: { top: "A", bottom: "P", left: "R", right: "L" },
  coronal: { top: "S", bottom: "I", left: "R", right: "L" },
  sagittal: { top: "S", bottom: "I", left: "A", right: "P" },
};

interface MprViewerProps {
  imageUrls: string[];
  findings: Finding[];
  overlay?: StudyOverlay;
}

/** Maps a toolbar tool id to the Cornerstone3D tool class name. */
const TOOL_NAME = MPR_TOOL_NAME;
const PRIMARY_CANDIDATES = MPR_PRIMARY_TOOLS;

/**
 * Multiplanar (MPR) viewer with full interaction.
 *
 *   - Left drag   = active tool (window/level, pan, zoom, rotate, crosshairs, measure…)
 *   - Right drag  = zoom
 *   - Middle drag = pan
 *   - Mouse wheel = scroll slices
 *
 * Supports crosshairs (synced slice navigation + reference lines across planes),
 * invert, reset, screenshot, and a single-pane / 2x2 layout toggle with a 3D
 * volume viewport in the fourth quadrant. Falls back to 2D stack viewports if
 * volume construction fails.
 */
export function MprViewer({ imageUrls, findings, overlay }: MprViewerProps) {
  const reactId = useId().replace(/[:]/g, "");
  const engineId = `mpr-engine-${reactId}`;
  const toolGroupId = `mpr-tg-${reactId}`;
  const refs = {
    axial: useRef<HTMLDivElement>(null),
    coronal: useRef<HTMLDivElement>(null),
    sagittal: useRef<HTMLDivElement>(null),
  };
  const layoutHostRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const engineStateRef = useRef<EngineState | null>(null);
  const labelmapBuildRef = useRef(0);
  const labelmapRef = useRef<{ built: BuiltLabelmap; repUID: string } | null>(null);

  const [status, setStatus] = useState<"loading" | "ready" | "no-image">("loading");
  const [engineGen, setEngineGen] = useState(0);
  const [mode, setMode] = useState<"volume" | "stack">("volume");
  const [labelmapActive, setLabelmapActive] = useState(false);
  const [axialSlice, setAxialSlice] = useState({ index: 0, count: imageUrls.length });

  const wlPreset = useViewerStore((s) => s.wlPreset);
  const invert = useViewerStore((s) => s.invert);
  const activeTool = useViewerStore((s) => s.activeTool);
  const singleView = useViewerStore((s) => s.singleView);
  const showAnnotations = useViewerStore((s) => s.showAnnotations);
  const showSegmentations = useViewerStore((s) => s.showSegmentations);
  const segOpacity = useViewerStore((s) => s.segOpacity);
  const hiddenSegIds = useViewerStore((s) => s.hiddenSegIds);
  const selectedFindingId = useViewerStore((s) => s.selectedFindingId);
  const resetNonce = useViewerStore((s) => s.resetNonce);
  const screenshotNonce = useViewerStore((s) => s.screenshotNonce);
  const zoomNonce = useViewerStore((s) => s.zoomNonce);
  const zoomDirection = useViewerStore((s) => s.zoomDirection);
  const setLabelmapSegId = useViewerStore((s) => s.setLabelmapSegId);

  useEffect(() => {
    let engine: { destroy: () => void } | null = null;
    let cancelled = false;

    async function setup() {
      if (imageUrls.length === 0) {
        setStatus("no-image");
        return;
      }
      const ok = await initCornerstone();
      if (!ok || cancelled) {
        setStatus("no-image");
        return;
      }

      const cs = (await import("@cornerstonejs/core")) as any;
      const csTools = (await import("@cornerstonejs/tools")) as any;
      const { RenderingEngine, Enums, volumeLoader, setVolumesForViewports } = cs;
      const { ViewportType, OrientationAxis } = Enums;
      const imageIds = imageUrls.map(imageIdFromUrl);
      const voiRange = wlToRange(wlPreset.windowWidth, wlPreset.windowCenter);

      const renderingEngine = new RenderingEngine(engineId);
      engine = renderingEngine;

      let ready = false;
      let resolvedMode: "volume" | "stack" = "volume";
      try {
        const viewportInputs = VIEWS.map((view) => ({
          viewportId: view,
          element: refs[view].current as HTMLDivElement,
          type: ViewportType.ORTHOGRAPHIC,
          defaultOptions: {
            orientation:
              view === "axial"
                ? OrientationAxis.AXIAL
                : view === "coronal"
                  ? OrientationAxis.CORONAL
                  : OrientationAxis.SAGITTAL,
            background: [0, 0, 0] as [number, number, number],
          },
        }));
        renderingEngine.setViewports(viewportInputs);

        const volumeId = `${VOLUME_LOADER_SCHEME}:${engineId}`;
        const volume = await volumeLoader.createAndCacheVolume(volumeId, { imageIds });
        if (cancelled) return;
        await volume.load();

        await setVolumesForViewports(renderingEngine, [{ volumeId }], VIEWS);
        if (cancelled) return;

        engineStateRef.current = { mode: "volume", volumeId, imageIds, voiRange };

        VIEWS.forEach((view) => {
          const vp = renderingEngine.getViewport(view);
          vp.setProperties?.({ voiRange, invert });
          vp.resetCamera?.();
        });
        renderingEngine.resize(true, true);
        resolvedMode = "volume";
        setMode("volume");
        ready = true;
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("MPR volume setup failed; falling back to 2D stack.", err);
      }

      if (!ready) {
        try {
          const viewportInputs = VIEWS.map((view) => ({
            viewportId: view,
            element: refs[view].current as HTMLDivElement,
            type: ViewportType.STACK,
          }));
          renderingEngine.setViewports(viewportInputs);
          const middle = Math.floor(imageIds.length / 2);
          await Promise.all(
            VIEWS.map(async (view) => {
              const vp = renderingEngine.getViewport(view);
              await vp.setStack(imageIds, middle);
              vp.setProperties?.({ voiRange, invert });
            }),
          );
          resolvedMode = "stack";
          setMode("stack");
          engineStateRef.current = { mode: "stack", volumeId: "", imageIds, voiRange };
          ready = true;
        } catch (err2) {
          // eslint-disable-next-line no-console
          console.warn("Stack fallback failed:", err2);
          if (!cancelled) setStatus("no-image");
          return;
        }
      }

      // ---- Tool group: bind mouse interactions to all panes ----
      try {
        setupToolGroup(
          csTools,
          toolGroupId,
          engineId,
          resolvedMode,
          useViewerStore.getState().activeTool,
        );
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("Tool group setup failed:", err);
      }

      renderingEngine.render();
      if (!cancelled) {
        setStatus("ready");
        setEngineGen((g) => g + 1);
        scheduleViewportSync(engineId, toolGroupId, refs, engineStateRef);
      }
    }

    setup();
    return () => {
      cancelled = true;
      engineStateRef.current = null;
      (async () => {
        try {
          const csTools = (await import("@cornerstonejs/tools")) as any;
          csTools.ToolGroupManager.destroyToolGroup(toolGroupId);
        } catch {
          /* noop */
        }
        try {
          engine?.destroy();
        } catch {
          /* noop */
        }
      })();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageUrls.join("|")]);

  // Switch the primary (left-button) tool when the toolbar selection changes.
  useEffect(() => {
    if (status !== "ready") return;
    (async () => {
      try {
        const csTools = (await import("@cornerstonejs/tools")) as any;
        const tg = csTools.ToolGroupManager.getToolGroup(toolGroupId);
        if (tg) applyMprToolBindings(csTools, tg, TOOL_NAME[activeTool]);
      } catch {
        /* noop */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTool, status]);

  // Apply window/level + invert to all live viewports.
  useEffect(() => {
    if (status !== "ready") return;
    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const engineApi = cs.getRenderingEngine(engineId);
        const voiRange = wlToRange(wlPreset.windowWidth, wlPreset.windowCenter);
        VIEWS.forEach((view) => {
          const vp = engineApi?.getViewport(view);
          vp?.setProperties?.({ voiRange, invert });
          vp?.render?.();
        });
      } catch {
        /* noop */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wlPreset, invert, status]);

  // Reset cameras + properties.
  useEffect(() => {
    if (status !== "ready" || resetNonce === 0) return;
    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const engineApi = cs.getRenderingEngine(engineId);
        VIEWS.forEach((view) => {
          const vp = engineApi?.getViewport(view);
          vp?.resetCamera?.();
          vp?.resetProperties?.();
          vp?.render?.();
        });
      } catch {
        /* noop */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetNonce]);

  // Programmatic zoom from toolbar +/− buttons.
  useEffect(() => {
    if (status !== "ready" || zoomNonce === 0) return;
    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const engineApi = cs.getRenderingEngine(engineId);
        if (!engineApi) return;
        VIEWS.forEach((view) => {
          const vp = engineApi.getViewport(view);
          if (vp) zoomViewport(vp, zoomDirection);
        });
        engineApi.render();
      } catch {
        /* noop */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomNonce, zoomDirection, status]);

  // Re-bind Cornerstone viewports after layout switches (single ↔ grid, axial ↔ coronal…).
  useLayoutEffect(() => {
    if (status !== "ready" || !engineStateRef.current) return;
    let cancelled = false;
    const run = async () => {
      await waitForLayout();
      if (cancelled) return;
      await syncViewports(engineId, toolGroupId, refs, engineStateRef);
    };
    void run();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [singleView, status]);

  // Re-measure when the viewer container changes size.
  useEffect(() => {
    if (status !== "ready") return;
    const targets = [layoutHostRef.current, frameRef.current].filter(Boolean) as HTMLElement[];
    if (targets.length === 0) return;

    let raf = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        void syncViewports(engineId, toolGroupId, refs, engineStateRef);
      });
    });
    targets.forEach((el) => observer.observe(el));
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, singleView]);

  // Export a screenshot of the visible viewports.
  useEffect(() => {
    if (status !== "ready" || screenshotNonce === 0) return;
    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const engineApi = cs.getRenderingEngine(engineId);
        const views = singleView ? [singleView] : VIEWS;
        const canvases = views
          .map((v) => engineApi?.getViewport(v)?.getCanvas?.())
          .filter(Boolean) as HTMLCanvasElement[];
        downloadCanvases(canvases);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("Screenshot failed:", err);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screenshotNonce]);

  // Track axial slice index for segmentation contour / mask overlays.
  useEffect(() => {
    if (status !== "ready") return;
    const timer = window.setInterval(async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const vp = cs.getRenderingEngine(engineId)?.getViewport("axial");
        if (!vp) return;
        const index =
          vp.getSliceIndex?.() ??
          vp.getCurrentImageIdIndex?.() ??
          Math.floor(imageUrls.length / 2);
        const count = vp.getNumberOfSlices?.() ?? imageUrls.length;
        setAxialSlice((prev) =>
          prev.index === index && prev.count === count ? prev : { index, count },
        );
      } catch {
        /* noop */
      }
    }, 120);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, imageUrls.length]);

  // Build a 3D labelmap from the overlay ROIs so AI regions render across the
  // axial/coronal/sagittal planes (and the 3D pane), not just on axial.
  const overlayKey = (overlay?.rois ?? [])
    .map((r) => `${r.segmentation_id ?? r.label}:${r.contours?.length ?? 0}:${JSON.stringify(r.bbox ?? {})}`)
    .join("|");

  useEffect(() => {
    if (engineGen === 0 || mode !== "volume" || !overlay || overlayKey === "") {
      return;
    }
    let cancelled = false;
    // Fresh ids per build: a new derived volume gets a fresh GPU texture bound
    // to the current rendering context, avoiding stale cross-context textures
    // after the engine is recreated on a re-analyze.
    const buildN = (labelmapBuildRef.current += 1);
    const segmentationId = `mpr-seg-${reactId}-${buildN}`;
    const segVolumeId = `${VOLUME_LOADER_SCHEME}:seg-${engineId}-${buildN}`;

    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const csTools = (await import("@cornerstonejs/tools")) as any;
        const built = await buildLabelmap(cs, csTools, {
          referenceVolumeId: engineStateRef.current?.volumeId || `${VOLUME_LOADER_SCHEME}:${engineId}`,
          segmentationId,
          segVolumeId,
          overlay,
        });
        if (cancelled || !built) return;
        const repUID = await addLabelmapToToolGroup(csTools, toolGroupId, segmentationId);
        if (cancelled || !repUID) {
          teardownLabelmap(cs, csTools, { segmentationId, segVolumeId, toolGroupId, repUID });
          return;
        }
        labelmapRef.current = { built, repUID };
        applyLabelmapAppearance(csTools, toolGroupId, repUID, built.segments, {
          showSegmentations: useViewerStore.getState().showSegmentations,
          segOpacity: useViewerStore.getState().segOpacity,
          hiddenSegIds: useViewerStore.getState().hiddenSegIds,
        });
        setLabelmapActive(true);
        setLabelmapSegId(segmentationId);
        cs.getRenderingEngine(engineId)?.render();
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("Labelmap build failed:", err);
      }
    })();
    return () => {
      cancelled = true;
      labelmapRef.current = null;
      setLabelmapActive(false);
      setLabelmapSegId(null);
      (async () => {
        try {
          const cs = (await import("@cornerstonejs/core")) as any;
          const csTools = (await import("@cornerstonejs/tools")) as any;
          teardownLabelmap(cs, csTools, { segmentationId, segVolumeId, toolGroupId });
        } catch {
          /* noop */
        }
      })();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engineGen, mode, overlayKey]);

  // Re-apply mask toggle / opacity / per-ROI visibility without rebuilding voxels.
  useEffect(() => {
    if (!labelmapActive || !labelmapRef.current) return;
    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const csTools = (await import("@cornerstonejs/tools")) as any;
        const { repUID, built } = labelmapRef.current!;
        applyLabelmapAppearance(csTools, toolGroupId, repUID, built.segments, {
          showSegmentations,
          segOpacity,
          hiddenSegIds,
        });
        cs.getRenderingEngine(engineId)?.render();
      } catch {
        /* noop */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [labelmapActive, showSegmentations, segOpacity, hiddenSegIds]);

  const currentZMm =
    overlay?.slice_z_mm?.length && overlay.slice_z_mm[axialSlice.index] != null
      ? overlay.slice_z_mm[axialSlice.index]
      : null;

  const show3dPane = singleView === null || singleView === "volume3d";
  const isSingleLayout = singleView !== null;

  const mprPanes = VIEWS.map((view) => {
    const isActive = singleView === null || singleView === view;
    return (
      <div
        key={view}
        className={[
          isSingleLayout
            ? [
                "absolute inset-0 h-full w-full",
                isActive ? "z-10 visible" : "pointer-events-none invisible",
              ].join(" ")
            : "h-full min-h-0 overflow-hidden rounded-md border border-surface-800",
        ].join(" ")}
        aria-hidden={isSingleLayout ? !isActive : undefined}
      >
        <Pane
          view={view}
          elRef={refs[view]}
          mode={mode}
          status={status}
          findings={findings}
          showAnnotations={showAnnotations}
          selectedFindingId={selectedFindingId}
          overlay={overlay}
          showSegmentations={showSegmentations}
          segOpacity={segOpacity}
          hiddenSegIds={hiddenSegIds}
          axialSlice={axialSlice}
          currentZMm={currentZMm}
          labelmapActive={labelmapActive}
        />
      </div>
    );
  });

  const volume3dPane =
    show3dPane && (
      <div
        className={
          isSingleLayout
            ? [
                "absolute inset-0 h-full w-full",
                singleView === "volume3d" ? "z-10 visible" : "pointer-events-none invisible",
              ].join(" ")
            : "h-full min-h-0 overflow-hidden rounded-md border border-surface-800"
        }
        aria-hidden={isSingleLayout ? singleView !== "volume3d" : undefined}
      >
        <VolumeViewport imageUrls={imageUrls} />
      </div>
    );

  return (
    <div
      ref={layoutHostRef}
      className={
        isSingleLayout
          ? "viewer-single-host min-h-0 flex-1"
          : "grid min-h-0 flex-1 grid-cols-2 grid-rows-2 gap-1 p-1"
      }
    >
      <div
        ref={frameRef}
        className={isSingleLayout ? "viewer-single-frame relative" : "contents"}
      >
        {mprPanes}
        {volume3dPane}
      </div>
    </div>
  );
}

interface PaneProps {
  view: View;
  elRef: React.RefObject<HTMLDivElement>;
  mode: "volume" | "stack";
  status: "loading" | "ready" | "no-image";
  findings: Finding[];
  showAnnotations: boolean;
  selectedFindingId: string | null;
  overlay?: StudyOverlay;
  showSegmentations: boolean;
  segOpacity: Record<string, number>;
  hiddenSegIds: Record<string, boolean>;
  axialSlice: { index: number; count: number };
  currentZMm: number | null;
  labelmapActive: boolean;
}

function Pane({
  view,
  elRef,
  mode,
  status,
  findings,
  showAnnotations,
  selectedFindingId,
  overlay,
  showSegmentations,
  segOpacity,
  hiddenSegIds,
  axialSlice,
  currentZMm,
  labelmapActive,
}: PaneProps) {
  const overlayHere = mode === "stack" || view === "axial";
  const wlPreset = useViewerStore((s) => s.wlPreset);
  const orient = ORIENTATION_LABELS[view];
  const showSlice = view === "axial" && axialSlice.count > 0;

  return (
    <div className="relative h-full w-full">
      <div ref={elRef} className="cs-viewport h-full w-full" onContextMenu={(e) => e.preventDefault()} />

      {/* VolView-style orientation labels */}
      {status === "ready" && (
        <div className="pointer-events-none absolute inset-0 z-10 select-none text-[11px] font-semibold text-slate-300/80">
          <span className="absolute left-1/2 top-1 -translate-x-1/2">{orient.top}</span>
          <span className="absolute bottom-1 left-1/2 -translate-x-1/2">{orient.bottom}</span>
          <span className="absolute left-1.5 top-1/2 -translate-y-1/2">{orient.left}</span>
          <span className="absolute right-1.5 top-1/2 -translate-y-1/2">{orient.right}</span>
        </div>
      )}

      {/* Pane title tab (top-left) */}
      <div
        className="absolute left-2 top-1.5 z-10 rounded bg-black/40 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider backdrop-blur-sm"
        style={{ color: REFERENCE_COLORS[view] }}
      >
        {view}
      </div>

      {/* Info icon (top-right) */}
      <div
        className="absolute right-2 top-1.5 z-10 text-slate-400/70"
        title={`${view} · W ${wlPreset.windowWidth} / L ${wlPreset.windowCenter}`}
      >
        <IconInfo width={14} height={14} />
      </div>

      {/* Slice + W/L readout (bottom-left) */}
      {status === "ready" && (
        <div className="pointer-events-none absolute bottom-1.5 left-2 z-10 space-y-0.5 text-[10px] leading-tight text-slate-400/80">
          {showSlice && (
            <div>
              Slice: {axialSlice.index + 1}/{axialSlice.count}
            </div>
          )}
          <div>
            W/L: {wlPreset.windowWidth.toFixed(2)} / {wlPreset.windowCenter.toFixed(2)}
          </div>
        </div>
      )}

      {status === "no-image" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="rounded-md bg-surface-850/80 px-3 py-2 text-center text-xs text-slate-400">
            No renderable pixel data.
            <br />
            AI overlays shown below.
          </div>
        </div>
      )}

      {view === "axial" && !labelmapActive && (
        <SegmentationOverlay
          overlay={overlay}
          sliceIndex={axialSlice.index}
          sliceCount={axialSlice.count}
          currentZMm={currentZMm}
          show={showSegmentations}
          segOpacity={segOpacity}
          hiddenSegIds={hiddenSegIds}
        />
      )}

      {showAnnotations && overlayHere && (
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {findings.map((f) => {
            const b = f.bbox || {};
            const x = (b.x ?? 0.4) * 100;
            const y = (b.y ?? 0.4) * 100;
            const w = (b.w ?? 0.15) * 100;
            const h = (b.h ?? 0.15) * 100;
            const selected = selectedFindingId === f.id;
            return (
              <g key={f.id}>
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill="none"
                  stroke={selected ? "#38bdf8" : "#f59e0b"}
                  strokeWidth={selected ? 0.7 : 0.4}
                  vectorEffect="non-scaling-stroke"
                />
                <text
                  x={x}
                  y={Math.max(y - 1.5, 3)}
                  fill={selected ? "#38bdf8" : "#f59e0b"}
                  fontSize="2.6"
                  fontWeight="600"
                >
                  {f.label} {Math.round(f.confidence * 100)}%
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

/** Create the tool group, register tools + mouse bindings, and add all viewports. */
function setupToolGroup(
  csTools: any,
  toolGroupId: string,
  engineId: string,
  mode: "volume" | "stack",
  activeTool: ToolName,
) {
  const { ToolGroupManager } = csTools;
  ToolGroupManager.destroyToolGroup(toolGroupId);
  const tg = ToolGroupManager.createToolGroup(toolGroupId);

  // Crosshairs only work on volume (orthographic) viewports.
  const supportsCrosshairs = mode === "volume";
  PRIMARY_CANDIDATES.forEach((name) => {
    if (name === "Crosshairs") {
      if (supportsCrosshairs) {
        tg.addTool("Crosshairs", {
          getReferenceLineColor: (id: View) => REFERENCE_COLORS[id] ?? "rgb(200,200,200)",
          getReferenceLineControllable: () => true,
          getReferenceLineDraggableRotatable: () => true,
          getReferenceLineSlabThicknessControlsOn: () => false,
        });
      }
    } else {
      tg.addTool(name);
    }
  });
  tg.addTool("StackScrollMouseWheel");

  // Register the segmentation display tool up front so labelmap representations
  // can render reliably (lazy registration races with tool-group recreation).
  try {
    tg.addTool(csTools.SegmentationDisplayTool.toolName);
    tg.setToolEnabled(csTools.SegmentationDisplayTool.toolName);
  } catch {
    /* noop */
  }

  VIEWS.forEach((view) => tg.addViewport(view, engineId));

  let primary = TOOL_NAME[activeTool];
  if (primary === "Crosshairs" && !supportsCrosshairs) primary = "WindowLevel";
  applyMprToolBindings(csTools, tg, primary);
}

/** Composite one or more viewport canvases horizontally and trigger a PNG download. */
function downloadCanvases(canvases: HTMLCanvasElement[]) {
  if (canvases.length === 0) return;
  const gap = 4;
  const height = Math.max(...canvases.map((c) => c.height));
  const width = canvases.reduce((sum, c) => sum + c.width, 0) + gap * (canvases.length - 1);
  const out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const ctx = out.getContext("2d");
  if (!ctx) return;
  ctx.fillStyle = "black";
  ctx.fillRect(0, 0, width, height);
  let x = 0;
  for (const c of canvases) {
    ctx.drawImage(c, x, 0);
    x += c.width + gap;
  }
  out.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lumira-screenshot-${Date.now()}.png`;
    a.click();
    URL.revokeObjectURL(url);
  }, "image/png");
}

function wlToRange(width: number, center: number) {
  return { lower: center - width / 2, upper: center + width / 2 };
}

type EngineState = {
  mode: "volume" | "stack";
  volumeId: string;
  imageIds: string[];
  voiRange: { lower: number; upper: number };
};

type ViewRefs = Record<View, React.RefObject<HTMLDivElement>>;

function waitForLayout() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

function scheduleViewportSync(
  engineId: string,
  toolGroupId: string,
  refs: ViewRefs,
  stateRef: React.MutableRefObject<EngineState | null>,
) {
  void waitForLayout().then(() => syncViewports(engineId, toolGroupId, refs, stateRef));
}

async function syncViewports(
  engineId: string,
  toolGroupId: string,
  refs: ViewRefs,
  stateRef: React.MutableRefObject<EngineState | null>,
) {
  const state = stateRef.current;
  if (!state) return;
  if (!refs.axial.current || !refs.coronal.current || !refs.sagittal.current) return;

  try {
    const cs = (await import("@cornerstonejs/core")) as any;
    const engine = cs.getRenderingEngine(engineId);
    if (!engine) return;

    const { Enums, setVolumesForViewports } = cs;
    const { ViewportType, OrientationAxis } = Enums;
    const invert = useViewerStore.getState().invert;

    if (state.mode === "volume") {
      engine.setViewports(
        VIEWS.map((view) => ({
          viewportId: view,
          element: refs[view].current as HTMLDivElement,
          type: ViewportType.ORTHOGRAPHIC,
          defaultOptions: {
            orientation:
              view === "axial"
                ? OrientationAxis.AXIAL
                : view === "coronal"
                  ? OrientationAxis.CORONAL
                  : OrientationAxis.SAGITTAL,
            background: [0, 0, 0] as [number, number, number],
          },
        })),
      );
      await setVolumesForViewports(engine, [{ volumeId: state.volumeId }], VIEWS);
    } else {
      engine.setViewports(
        VIEWS.map((view) => ({
          viewportId: view,
          element: refs[view].current as HTMLDivElement,
          type: ViewportType.STACK,
        })),
      );
      const middle = Math.floor(state.imageIds.length / 2);
      await Promise.all(
        VIEWS.map(async (view) => {
          const vp = engine.getViewport(view);
          await vp.setStack(state.imageIds, middle);
        }),
      );
    }

    VIEWS.forEach((view) => {
      const vp = engine.getViewport(view);
      vp?.setProperties?.({ voiRange: state.voiRange, invert });
      vp?.resetCamera?.();
      vp?.render?.();
    });
    engine.resize(true, true);
    engine.render();

    try {
      const csTools = (await import("@cornerstonejs/tools")) as any;
      const tg = csTools.ToolGroupManager.getToolGroup(toolGroupId);
      if (tg) {
        VIEWS.forEach((view) => {
          try {
            tg.addViewport(view, engineId);
          } catch {
            /* already bound */
          }
        });
        const active = useViewerStore.getState().activeTool;
        applyMprToolBindings(csTools, tg, TOOL_NAME[active]);
      }
    } catch {
      /* noop */
    }
  } catch {
    /* noop */
  }
}
