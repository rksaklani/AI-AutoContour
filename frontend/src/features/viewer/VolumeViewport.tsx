import { useEffect, useId, useRef, useState } from "react";

import { Spinner } from "@/components/ui";
import { imageIdFromUrl, initCornerstone, VOLUME_LOADER_SCHEME } from "@/lib/cornerstoneInit";

const PRESETS = ["CT-Bone", "CT-Lung", "CT-Soft-Tissue", "CT-AAA", "CT-Cardiac", "MR-Default"];

interface VolumeViewportProps {
  imageUrls: string[];
  /** Show preset selector below the viewport (fullscreen panel). */
  showPresetBar?: boolean;
}

/**
 * Embeddable 3D volume viewport (Cornerstone3D VOLUME_3D).
 * Left drag = rotate, right = zoom, middle = pan.
 */
export function VolumeViewport({ imageUrls, showPresetBar = false }: VolumeViewportProps) {
  const reactId = useId().replace(/[:]/g, "");
  const engineId = `vr-engine-${reactId}`;
  const toolGroupId = `vr-tg-${reactId}`;
  const viewportId = "vr3d";
  const elRef = useRef<HTMLDivElement>(null);

  const [preset, setPreset] = useState(PRESETS[0]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let engine: { destroy: () => void } | null = null;
    let cancelled = false;

    async function setup() {
      if (imageUrls.length === 0) {
        setStatus("error");
        return;
      }
      const ok = await initCornerstone();
      if (!ok || cancelled) {
        setStatus("error");
        return;
      }
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const csTools = (await import("@cornerstonejs/tools")) as any;
        const { RenderingEngine, Enums, volumeLoader, setVolumesForViewports } = cs;
        const { ViewportType } = Enums;

        const renderingEngine = new RenderingEngine(engineId);
        engine = renderingEngine;
        renderingEngine.setViewports([
          {
            viewportId,
            element: elRef.current as HTMLDivElement,
            type: ViewportType.VOLUME_3D,
            defaultOptions: { background: [0, 0, 0] as [number, number, number] },
          },
        ]);

        const imageIds = imageUrls.map(imageIdFromUrl);
        const volumeId = `${VOLUME_LOADER_SCHEME}:vr-${engineId}`;
        const volume = await volumeLoader.createAndCacheVolume(volumeId, { imageIds });
        if (cancelled) return;
        volume.load();

        await setVolumesForViewports(renderingEngine, [{ volumeId }], [viewportId]);
        if (cancelled) return;

        const vp = renderingEngine.getViewport(viewportId);
        vp.setProperties({ preset });
        vp.resetCamera();
        renderingEngine.render();

        const { ToolGroupManager, Enums: tEnums } = csTools;
        const { MouseBindings } = tEnums;
        ToolGroupManager.destroyToolGroup(toolGroupId);
        const tg = ToolGroupManager.createToolGroup(toolGroupId);
        tg.addTool("TrackballRotate");
        tg.addTool("Zoom");
        tg.addTool("Pan");
        tg.addViewport(viewportId, engineId);
        tg.setToolActive("TrackballRotate", { bindings: [{ mouseButton: MouseBindings.Primary }] });
        tg.setToolActive("Zoom", { bindings: [{ mouseButton: MouseBindings.Secondary }] });
        tg.setToolActive("Pan", { bindings: [{ mouseButton: MouseBindings.Auxiliary }] });

        if (!cancelled) setStatus("ready");
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("3D volume render failed:", err);
        if (!cancelled) setStatus("error");
      }
    }

    setup();
    return () => {
      cancelled = true;
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

  useEffect(() => {
    if (status !== "ready") return;
    (async () => {
      try {
        const cs = (await import("@cornerstonejs/core")) as any;
        const vp = cs.getRenderingEngine(engineId)?.getViewport(viewportId);
        vp?.setProperties({ preset });
        vp?.render();
      } catch {
        /* noop */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset, status]);

  const presetControl = (
    <select
      className="rounded bg-surface-900/80 px-1.5 py-0.5 text-[10px] text-slate-200"
      value={preset}
      onChange={(e) => setPreset(e.target.value)}
      onClick={(e) => e.stopPropagation()}
    >
      {PRESETS.map((p) => (
        <option key={p} value={p}>
          {p}
        </option>
      ))}
    </select>
  );

  return (
    <div className={showPresetBar ? "flex h-full flex-col gap-3" : "relative h-full w-full"}>
      <div
        className={
          showPresetBar
            ? "relative flex-1 overflow-hidden rounded-md border border-surface-700 bg-black"
            : "relative h-full w-full"
        }
      >
        <div
          className="absolute left-2 top-1.5 z-10 text-[11px] font-semibold uppercase tracking-wider text-violet-400"
        >
          3D
        </div>
        <div ref={elRef} className="cs-viewport h-full w-full" onContextMenu={(e) => e.preventDefault()} />

        {status === "loading" && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <Spinner className="h-6 w-6" />
          </div>
        )}
        {status === "error" && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="rounded-md bg-surface-850/80 px-3 py-2 text-center text-xs text-slate-400">
              3D volume unavailable
            </div>
          </div>
        )}
        {status === "ready" && !showPresetBar && (
          <div className="absolute bottom-1.5 right-1.5 z-10">{presetControl}</div>
        )}
        {status === "ready" && showPresetBar && (
          <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-surface-900/70 px-2 py-1 text-[10px] text-slate-400">
            Left: rotate · Right: zoom · Middle: pan
          </div>
        )}
      </div>

      {showPresetBar && (
        <div className="flex items-center gap-2">
          <label className="text-[11px] uppercase tracking-wider text-slate-500">Preset</label>
          {presetControl}
        </div>
      )}
    </div>
  );
}
