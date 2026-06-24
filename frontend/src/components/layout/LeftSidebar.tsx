import { Badge } from "@/components/ui";
import { MeasurementsPanel } from "@/features/viewer/MeasurementsPanel";
import { RenderingControls } from "@/features/viewer/RenderingControls";
import { TagBrowser } from "@/features/studies/TagBrowser";
import { useViewerStore } from "@/store/viewerStore";
import type { Segmentation, Study } from "@/types";

export function LeftSidebar({
  study,
  segmentations,
}: {
  study: Study;
  segmentations: Segmentation[];
}) {
  const leftTab = useViewerStore((s) => s.leftTab);
  const selectedSeriesId = useViewerStore((s) => s.selectedSeriesId);
  const setSelectedSeriesId = useViewerStore((s) => s.setSelectedSeriesId);
  const segOpacity = useViewerStore((s) => s.segOpacity);
  const hiddenSegIds = useViewerStore((s) => s.hiddenSegIds);
  const setSegOpacity = useViewerStore((s) => s.setSegOpacity);
  const toggleSegVisibility = useViewerStore((s) => s.toggleSegVisibility);

  const imageSeries = study.series.filter(
    (s) => !["RTSTRUCT", "RTPLAN", "RTDOSE"].includes((s.modality || "").toUpperCase()),
  );

  return (
    <aside className="flex w-64 shrink-0 flex-col gap-3 overflow-auto border-r border-surface-700 bg-surface-900 p-3">
      {leftTab === "data" && (
        <>
          <div className="panel p-3">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Patient
            </h3>
            <dl className="space-y-1 text-sm">
              <Row label="Name" value={study.patient_name || "—"} />
              <Row label="ID" value={study.patient_id || "—"} />
              <Row
                label="Sex / Age"
                value={`${study.patient_sex || "—"} / ${study.patient_age || "—"}`}
              />
              <Row label="Modality" value={study.modality || "—"} />
              <Row label="Body part" value={study.body_part || "—"} />
            </dl>
          </div>

          <div className="panel p-3">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Series ({study.series.length})
            </h3>
            <ul className="space-y-1">
              <SeriesRow
                label="All image series"
                count={imageSeries.reduce((n, s) => n + s.instance_count, 0)}
                active={selectedSeriesId === null}
                onClick={() => setSelectedSeriesId(null)}
              />
              {imageSeries.map((s) => (
                <SeriesRow
                  key={s.id}
                  label={s.description || s.modality || "Series"}
                  count={s.instance_count}
                  active={selectedSeriesId === s.id}
                  onClick={() => setSelectedSeriesId(s.id)}
                />
              ))}
              {study.series.length === 0 && (
                <li className="text-xs text-slate-500">No series uploaded.</li>
              )}
            </ul>
          </div>

          <div className="panel p-3">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Layers ({segmentations.length})
            </h3>
            <ul className="space-y-2">
              {segmentations.map((seg) => {
                const hidden = Boolean(hiddenSegIds[seg.id]);
                const opacity = segOpacity[seg.id] ?? 0.45;
                return (
                  <li key={seg.id} className="rounded bg-surface-800 p-2 text-xs">
                    <div className="mb-1 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => toggleSegVisibility(seg.id)}
                        className="inline-block h-3 w-3 shrink-0 rounded-sm border border-surface-600"
                        style={{
                          backgroundColor: hidden ? "transparent" : seg.color,
                          opacity: hidden ? 0.4 : 1,
                        }}
                        title={hidden ? "Show structure" : "Hide structure"}
                      />
                      <span className="flex-1 truncate text-slate-300">{seg.label}</span>
                      <Badge>{seg.structure_type}</Badge>
                    </div>
                    <label className="flex items-center gap-2 text-[10px] text-slate-500">
                      <span className="w-12">Opacity</span>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={opacity}
                        disabled={hidden}
                        onChange={(e) => setSegOpacity(seg.id, Number(e.target.value))}
                        className="flex-1"
                      />
                      <span className="w-8 text-right">{Math.round(opacity * 100)}%</span>
                    </label>
                  </li>
                );
              })}
              {segmentations.length === 0 && (
                <li className="text-xs text-slate-500">Run analysis to generate masks.</li>
              )}
            </ul>
          </div>

          <TagBrowser study={study} />
        </>
      )}

      {leftTab === "annotations" && <MeasurementsPanel />}

      {leftTab === "rendering" && <RenderingControls />}
    </aside>
  );
}

function SeriesRow({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs transition-colors ${
          active
            ? "bg-brand-600/20 text-brand-300"
            : "bg-surface-800 text-slate-300 hover:bg-surface-700"
        }`}
      >
        <span className="truncate">{label}</span>
        <span className="ml-2 shrink-0 text-slate-500">{count}</span>
      </button>
    </li>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="truncate text-right text-slate-200">{value}</dd>
    </div>
  );
}
