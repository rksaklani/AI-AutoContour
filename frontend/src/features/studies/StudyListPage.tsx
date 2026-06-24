import { useNavigate } from "react-router-dom";

import { useStudies } from "@/api/studies";
import { TopBar } from "@/components/layout/TopBar";
import { Badge, EmptyState, Spinner } from "@/components/ui";
import { UploadDialog } from "@/features/studies/UploadDialog";
import { useState } from "react";

const STATUS_TONE: Record<string, "default" | "brand" | "low" | "moderate" | "high"> = {
  uploaded: "default",
  processing: "brand",
  analyzed: "low",
  reported: "low",
  error: "high",
};

export function StudyListPage() {
  const { data: studies, isLoading } = useStudies();
  const navigate = useNavigate();
  const [showUpload, setShowUpload] = useState(false);

  return (
    <div className="flex h-full flex-col bg-surface-950">
      <TopBar />
      <main className="mx-auto w-full max-w-6xl flex-1 overflow-auto p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">Studies</h1>
            <p className="text-sm text-slate-400">Upload and analyze medical imaging studies</p>
          </div>
          <button className="btn-primary" onClick={() => setShowUpload(true)}>
            + New study
          </button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-20">
            <Spinner className="h-6 w-6" />
          </div>
        ) : !studies || studies.length === 0 ? (
          <div className="panel">
            <EmptyState
              title="No studies yet"
              hint="Create a study and upload DICOM files to get started."
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {studies.map((s) => (
              <button
                key={s.id}
                onClick={() => navigate(`/studies/${s.id}`)}
                className="panel p-4 text-left transition-colors hover:border-brand-500"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-medium text-slate-100">
                    {s.patient_name || "Unknown patient"}
                  </span>
                  <Badge tone={STATUS_TONE[s.status] ?? "default"}>{s.status}</Badge>
                </div>
                <div className="text-sm text-slate-400">
                  {s.modality || "—"} · {s.body_part || "—"}
                </div>
                <div className="mt-1 truncate text-xs text-slate-500">
                  {s.description || "No description"}
                </div>
                <div className="mt-3 text-[11px] text-slate-600">
                  {new Date(s.created_at).toLocaleString()}
                </div>
              </button>
            ))}
          </div>
        )}
      </main>

      {showUpload && (
        <UploadDialog
          onClose={() => setShowUpload(false)}
          onCreated={(id) => {
            setShowUpload(false);
            navigate(`/studies/${id}`);
          }}
        />
      )}
    </div>
  );
}
