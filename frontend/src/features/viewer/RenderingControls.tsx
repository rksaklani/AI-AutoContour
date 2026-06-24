import clsx from "clsx";

import { useViewerStore, WL_PRESETS, type ViewLayout } from "@/store/viewerStore";

const LAYOUTS: { id: ViewLayout; label: string }[] = [
  { id: null, label: "2×2 MPR + 3D" },
  { id: "axial", label: "Axial" },
  { id: "coronal", label: "Coronal" },
  { id: "sagittal", label: "Sagittal" },
  { id: "volume3d", label: "3D" },
];

export function RenderingControls() {
  const show3D = useViewerStore((s) => s.show3D);
  const setShow3D = useViewerStore((s) => s.setShow3D);
  const singleView = useViewerStore((s) => s.singleView);
  const setSingleView = useViewerStore((s) => s.setSingleView);
  const wlPreset = useViewerStore((s) => s.wlPreset);
  const setWlPreset = useViewerStore((s) => s.setWlPreset);
  const invert = useViewerStore((s) => s.invert);
  const toggleInvert = useViewerStore((s) => s.toggleInvert);
  const showSeg = useViewerStore((s) => s.showSegmentations);
  const toggleSeg = useViewerStore((s) => s.toggleSegmentations);
  const showAnn = useViewerStore((s) => s.showAnnotations);
  const toggleAnn = useViewerStore((s) => s.toggleAnnotations);

  return (
    <div className="flex flex-col gap-3">
      <div className="panel p-3">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Mode
        </h3>
        <div className="grid grid-cols-2 gap-1">
          <SegBtn active={!show3D} onClick={() => setShow3D(false)}>
            2D MPR
          </SegBtn>
          <SegBtn active={show3D} onClick={() => setShow3D(true)}>
            3D Volume
          </SegBtn>
        </div>
      </div>

      {!show3D && (
        <div className="panel p-3">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Layout
          </h3>
          <div className="flex flex-col gap-1">
            {LAYOUTS.map((l) => (
              <SegBtn
                key={l.label}
                active={singleView === l.id}
                onClick={() => setSingleView(l.id)}
                full
              >
                {l.label}
              </SegBtn>
            ))}
          </div>
        </div>
      )}

      <div className="panel p-3">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Window / Level
        </h3>
        <select
          className="input !py-1.5 text-xs"
          value={wlPreset.name}
          onChange={(e) =>
            setWlPreset(WL_PRESETS.find((p) => p.name === e.target.value) ?? WL_PRESETS[0])
          }
        >
          {WL_PRESETS.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name} ({p.windowWidth} / {p.windowCenter})
            </option>
          ))}
        </select>
        <label className="mt-2 flex items-center gap-2 text-xs text-slate-300">
          <input type="checkbox" checked={invert} onChange={toggleInvert} />
          Invert grayscale
        </label>
      </div>

      <div className="panel p-3">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Overlays
        </h3>
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input type="checkbox" checked={showSeg} onChange={toggleSeg} />
          Segmentation masks
        </label>
        <label className="mt-1 flex items-center gap-2 text-xs text-slate-300">
          <input type="checkbox" checked={showAnn} onChange={toggleAnn} />
          AI annotations
        </label>
      </div>
    </div>
  );
}

function SegBtn({
  active,
  onClick,
  children,
  full,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "rounded px-2 py-1.5 text-xs font-medium transition-colors",
        full ? "w-full text-left" : "text-center",
        active ? "bg-brand-600 text-white" : "bg-surface-800 text-slate-300 hover:bg-surface-700",
      )}
    >
      {children}
    </button>
  );
}
