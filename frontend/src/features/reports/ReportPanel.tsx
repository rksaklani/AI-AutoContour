import { useState } from "react";

import { downloadReport, useGenerateReport, useReports } from "@/api/reports";
import { Panel, Spinner } from "@/components/ui";

export function ReportPanel({ studyId, canReport }: { studyId: string; canReport: boolean }) {
  const { data: reports } = useReports(studyId);
  const generate = useGenerateReport();
  const [error, setError] = useState<string | null>(null);

  const latest = reports?.[0];

  async function onGenerate() {
    setError(null);
    try {
      await generate.mutateAsync(studyId);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Report generation failed");
    }
  }

  return (
    <Panel
      title="Report"
      actions={
        <button
          className="btn-primary !px-2 !py-1 text-xs"
          onClick={onGenerate}
          disabled={generate.isPending || !canReport}
          title={canReport ? "" : "Run analysis first"}
        >
          {generate.isPending ? <Spinner /> : null}
          Generate
        </button>
      }
    >
      <div className="p-3">
        {!latest ? (
          <p className="text-xs text-slate-500">
            {canReport
              ? "Generate a structured report (PDF / DOCX / HTML)."
              : "Analyze the study to enable reporting."}
          </p>
        ) : (
          <div className="space-y-3">
            <div className="rounded-md bg-surface-800 p-2 text-xs text-slate-400">
              <div>
                Findings: <span className="text-slate-200">{String(latest.summary.findings ?? 0)}</span>
              </div>
              <div>
                Generated: <span className="text-slate-200">{new Date(latest.created_at).toLocaleString()}</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {(["pdf", "docx", "html"] as const).map((fmt) => (
                <button
                  key={fmt}
                  className="btn-ghost text-xs uppercase"
                  disabled={!latest.formats.includes(fmt)}
                  onClick={() => downloadReport(latest.id, fmt)}
                >
                  {fmt}
                </button>
              ))}
            </div>
          </div>
        )}
        {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
      </div>
    </Panel>
  );
}
