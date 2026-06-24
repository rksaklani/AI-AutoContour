import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  IconAngle,
  IconCamera,
  IconCrosshair,
  IconCube,
  IconEllipse,
  IconFolderOpen,
  IconInvert,
  IconLayoutGrid,
  IconPan,
  IconPolygon,
  IconRectangle,
  IconReset,
  IconRotate,
  IconRuler,
  IconSave,
  IconScroll,
  IconText,
  IconWindowLevel,
  IconZoom,
} from "@/components/icons";
import { saveViewerSession } from "@/lib/viewerSession";
import { useViewerStore, type ToolName, type ViewLayout } from "@/store/viewerStore";

type IconType = React.ComponentType<React.SVGProps<SVGSVGElement>>;

/** Tool, label, and single-key shortcut (VolView-style hints). */
const TOOL_ITEMS: { id: ToolName; label: string; key: string; Icon: IconType }[] = [
  { id: "WindowLevel", label: "Window / Level", key: "w", Icon: IconWindowLevel },
  { id: "Pan", label: "Pan", key: "n", Icon: IconPan },
  { id: "Zoom", label: "Zoom", key: "z", Icon: IconZoom },
  { id: "StackScroll", label: "Scroll slices", key: "s", Icon: IconScroll },
  { id: "Crosshairs", label: "Crosshairs", key: "c", Icon: IconCrosshair },
  { id: "Rotate", label: "Rotate", key: "o", Icon: IconRotate },
  { id: "Length", label: "Ruler", key: "l", Icon: IconRuler },
  { id: "Angle", label: "Angle", key: "a", Icon: IconAngle },
  { id: "RectangleROI", label: "Rectangle", key: "r", Icon: IconRectangle },
  { id: "EllipticalROI", label: "Ellipse", key: "e", Icon: IconEllipse },
  { id: "Probe", label: "Polygon / Probe", key: "g", Icon: IconPolygon },
  { id: "ArrowAnnotate", label: "Text", key: "t", Icon: IconText },
];

const SHORTCUTS: Record<string, ToolName> = Object.fromEntries(
  TOOL_ITEMS.map((t) => [t.key, t.id]),
) as Record<string, ToolName>;

type LayoutOption = { label: string; layout: ViewLayout; show3D: boolean };
const LAYOUT_OPTIONS: LayoutOption[] = [
  { label: "Quad View", layout: null, show3D: false },
  { label: "Axial Only", layout: "axial", show3D: false },
  { label: "Coronal Only", layout: "coronal", show3D: false },
  { label: "Sagittal Only", layout: "sagittal", show3D: false },
  { label: "3D Only", layout: "volume3d", show3D: false },
  { label: "3D Volume", layout: null, show3D: true },
];

function RailButton({
  label,
  hint,
  active,
  onClick,
  Icon,
}: {
  label: string;
  hint?: string;
  active?: boolean;
  onClick: () => void;
  Icon: IconType;
}) {
  return (
    <button
      type="button"
      title={hint ? `${label} [${hint}]` : label}
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
      className={clsx(
        "group relative flex h-10 w-10 items-center justify-center rounded-md transition-colors",
        active
          ? "bg-brand-600 text-white"
          : "text-slate-400 hover:bg-surface-700 hover:text-slate-100",
      )}
    >
      <Icon />
      <span className="pointer-events-none absolute left-12 z-30 flex items-center gap-1 whitespace-nowrap rounded bg-surface-700 px-2 py-1 text-xs text-slate-100 opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
        {label}
        {hint && (
          <kbd className="rounded bg-surface-900 px-1 text-[10px] uppercase text-slate-400">
            {hint}
          </kbd>
        )}
      </span>
    </button>
  );
}

function Divider() {
  return <div className="my-1 h-px w-7 bg-surface-700" />;
}

export function ToolRail({ studyId }: { studyId: string }) {
  const navigate = useNavigate();
  const activeTool = useViewerStore((s) => s.activeTool);
  const setActiveTool = useViewerStore((s) => s.setActiveTool);
  const invert = useViewerStore((s) => s.invert);
  const toggleInvert = useViewerStore((s) => s.toggleInvert);
  const resetView = useViewerStore((s) => s.resetView);
  const requestScreenshot = useViewerStore((s) => s.requestScreenshot);
  const zoomIn = useViewerStore((s) => s.zoomIn);
  const zoomOut = useViewerStore((s) => s.zoomOut);
  const setSingleView = useViewerStore((s) => s.setSingleView);
  const setShow3D = useViewerStore((s) => s.setShow3D);
  const singleView = useViewerStore((s) => s.singleView);
  const show3D = useViewerStore((s) => s.show3D);

  const [layoutOpen, setLayoutOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const layoutRef = useRef<HTMLDivElement>(null);

  // Close the layout menu on outside click.
  useEffect(() => {
    if (!layoutOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (layoutRef.current && !layoutRef.current.contains(e.target as Node)) {
        setLayoutOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [layoutOpen]);

  // Keyboard shortcuts for tools (ignored while typing in inputs).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (
        el &&
        (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)
      ) {
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const tool = SHORTCUTS[e.key.toLowerCase()];
      if (tool) {
        setActiveTool(tool);
        e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setActiveTool]);

  function applyLayout(opt: LayoutOption) {
    setShow3D(opt.show3D);
    setSingleView(opt.layout);
    setLayoutOpen(false);
  }

  function onSaveSession() {
    saveViewerSession(studyId);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1500);
  }

  return (
    <div className="flex w-14 shrink-0 flex-col items-center gap-1 overflow-y-auto border-r border-surface-700 bg-surface-900 py-2">
      <RailButton label="Open files" Icon={IconFolderOpen} onClick={() => navigate("/")} />
      <RailButton
        label={saved ? "Session saved" : "Save session"}
        Icon={IconSave}
        active={saved}
        onClick={onSaveSession}
      />

      <div ref={layoutRef} className="relative">
        <RailButton
          label="Layout"
          Icon={IconLayoutGrid}
          active={layoutOpen}
          onClick={() => setLayoutOpen((o) => !o)}
        />
        {layoutOpen && (
          <div className="absolute left-12 top-0 z-40 w-44 rounded-md border border-surface-700 bg-surface-850 py-1 shadow-xl">
            {LAYOUT_OPTIONS.map((opt) => {
              const isActive =
                opt.show3D === show3D &&
                (opt.show3D ? true : singleView === opt.layout);
              return (
                <button
                  key={opt.label}
                  type="button"
                  onClick={() => applyLayout(opt)}
                  className={clsx(
                    "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs",
                    isActive ? "text-brand-300" : "text-slate-300 hover:bg-surface-700",
                  )}
                >
                  <span
                    className={clsx(
                      "inline-block h-3 w-3 rounded-full border",
                      isActive ? "border-brand-400 bg-brand-500" : "border-surface-600",
                    )}
                  />
                  {opt.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <Divider />

      <RailButton label="Window / Level" hint="w" Icon={IconWindowLevel} active={activeTool === "WindowLevel"} onClick={() => setActiveTool("WindowLevel")} />
      {TOOL_ITEMS.filter((t) => t.id !== "WindowLevel").map((t) => (
        <RailButton
          key={t.id}
          label={t.label}
          hint={t.key}
          Icon={t.Icon}
          active={activeTool === t.id}
          onClick={() => setActiveTool(t.id)}
        />
      ))}

      <Divider />
      <RailButton label="Zoom in" hint="+" Icon={IconZoom} onClick={zoomIn} />
      <RailButton label="Zoom out" hint="-" Icon={IconZoom} onClick={zoomOut} />
      <RailButton
        label={invert ? "Invert (on)" : "Invert"}
        Icon={IconInvert}
        active={invert}
        onClick={toggleInvert}
      />
      <RailButton label="Reset / fit view" Icon={IconReset} onClick={resetView} />
      <RailButton label="3D view" Icon={IconCube} active={show3D} onClick={() => setShow3D(!show3D)} />
      <RailButton label="Screenshot" Icon={IconCamera} onClick={requestScreenshot} />
    </div>
  );
}
