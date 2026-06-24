import { Badge, EmptyState, Panel } from "@/components/ui";
import { useViewerStore } from "@/store/viewerStore";
import type { Finding } from "@/types";

const SEV_TONE: Record<string, "low" | "moderate" | "high"> = {
  low: "low",
  moderate: "moderate",
  high: "high",
};

export function FindingsPanel({ findings }: { findings: Finding[] }) {
  const selectedFindingId = useViewerStore((s) => s.selectedFindingId);
  const selectFinding = useViewerStore((s) => s.selectFinding);

  return (
    <Panel title={`AI Findings (${findings.length})`} className="flex-1">
      {findings.length === 0 ? (
        <EmptyState title="No findings yet" hint="Run AI analysis to detect abnormalities." />
      ) : (
        <ul className="divide-y divide-surface-700">
          {findings.map((f) => {
            const selected = selectedFindingId === f.id;
            return (
              <li
                key={f.id}
                onClick={() => selectFinding(selected ? null : f.id)}
                className={`cursor-pointer p-3 transition-colors ${
                  selected ? "bg-brand-600/10" : "hover:bg-surface-800"
                }`}
              >
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-medium text-slate-100">{f.label}</span>
                  <Badge tone={SEV_TONE[f.severity] ?? "moderate"}>{f.severity}</Badge>
                </div>
                <p className="text-xs text-slate-400">{f.location}</p>
                <div className="mt-2 flex gap-3 text-xs text-slate-400">
                  <span>
                    <span className="text-slate-500">Confidence:</span>{" "}
                    <span className="font-semibold text-brand-400">
                      {Math.round(f.confidence * 100)}%
                    </span>
                  </span>
                  {f.volume_cc != null && (
                    <span>
                      <span className="text-slate-500">Volume:</span> {f.volume_cc.toFixed(1)} cc
                    </span>
                  )}
                </div>
                {selected && (
                  <div className="mt-2 space-y-1 border-t border-surface-700 pt-2 text-xs">
                    <p className="text-slate-300">{f.description}</p>
                    <p className="text-amber-400/90">
                      <span className="text-slate-500">Recommendation:</span> {f.recommendation}
                    </p>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
