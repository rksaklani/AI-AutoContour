import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useAnalyze, useFindings, useSegmentations, useStudyOverlay } from "@/api/analysis";
import { useStudy } from "@/api/studies";
import { LeftSidebar } from "@/components/layout/LeftSidebar";
import { TopBar } from "@/components/layout/TopBar";
import { Spinner } from "@/components/ui";
import { AiDrawer } from "@/features/ai/AiDrawer";
import { ToolRail } from "@/features/viewer/ToolRail";
import { ViewerArea } from "@/features/viewer/ViewerArea";
import { loadViewerSession, saveViewerSession } from "@/lib/viewerSession";
import { subscribeJobProgress } from "@/lib/ws";
import { useViewerStore } from "@/store/viewerStore";
import type { JobProgressEvent } from "@/types";

const NON_IMAGE_MODALITIES = new Set(["RTSTRUCT", "RTPLAN", "RTDOSE", "SR", "PR"]);

export function WorkspacePage() {
  const { studyId } = useParams<{ studyId: string }>();
  const qc = useQueryClient();
  const { data: study, isLoading } = useStudy(studyId);
  const { data: findings = [] } = useFindings(studyId);
  const { data: segmentations = [] } = useSegmentations(studyId);
  const { data: overlay } = useStudyOverlay(studyId);
  const analyze = useAnalyze();

  const selectedSeriesId = useViewerStore((s) => s.selectedSeriesId);
  const initSegOpacities = useViewerStore((s) => s.initSegOpacities);

  const [progress, setProgress] = useState<JobProgressEvent | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const sessionLoadedRef = useRef(false);

  useEffect(() => () => cleanupRef.current?.(), []);

  // Restore viewer session from localStorage once per study.
  useEffect(() => {
    if (!studyId || sessionLoadedRef.current) return;
    loadViewerSession(studyId);
    sessionLoadedRef.current = true;
  }, [studyId]);

  // Persist viewer session on changes.
  useEffect(() => {
    if (!studyId) return;
    return useViewerStore.subscribe(() => saveViewerSession(studyId));
  }, [studyId]);

  // Default opacity for new segmentations.
  useEffect(() => {
    if (segmentations.length > 0) {
      initSegOpacities(segmentations.map((s) => s.id));
    }
  }, [segmentations, initSegOpacities]);

  async function onAnalyze() {
    if (!studyId) return;
    setProgress({ stage: "queued", progress: 0, status: "running" });
    const job = await analyze.mutateAsync(studyId);
    cleanupRef.current?.();
    cleanupRef.current = subscribeJobProgress(job.id, (event) => {
      setProgress(event);
      if (event.status === "completed" || event.status === "failed") {
        qc.invalidateQueries({ queryKey: ["findings", studyId] });
        qc.invalidateQueries({ queryKey: ["segmentations", studyId] });
        qc.invalidateQueries({ queryKey: ["overlay", studyId] });
        qc.invalidateQueries({ queryKey: ["study", studyId] });
        if (event.status === "completed") {
          setTimeout(() => setProgress(null), 1500);
        }
      }
    });
    if (job.status === "completed") {
      qc.invalidateQueries({ queryKey: ["findings", studyId] });
      qc.invalidateQueries({ queryKey: ["segmentations", studyId] });
      qc.invalidateQueries({ queryKey: ["overlay", studyId] });
      qc.invalidateQueries({ queryKey: ["study", studyId] });
      setProgress(null);
    }
  }

  const imageUrls = useMemo(() => {
    if (!study) return [];
    const seriesList = study.series.filter(
      (s) => !NON_IMAGE_MODALITIES.has((s.modality || "").toUpperCase()),
    );
    const active =
      selectedSeriesId != null
        ? seriesList.filter((s) => s.id === selectedSeriesId)
        : seriesList;
    return active.flatMap((s) =>
      s.instances.map((i) => i.url).filter((u): u is string => Boolean(u)),
    );
  }, [study, selectedSeriesId]);

  if (isLoading || !study) {
    return (
      <div className="flex h-full items-center justify-center bg-surface-950">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  const analyzed = ["analyzed", "reported"].includes(study.status);

  return (
    <div className="flex h-full flex-col bg-surface-950">
      <TopBar title={study.patient_name || "Study"} showTabs />

      <div className="flex items-center gap-3 border-b border-surface-700 bg-surface-900 px-4 py-2">
        <Link to="/" className="btn-ghost text-xs">
          ← Studies
        </Link>
        <button
          className="btn-primary text-sm"
          onClick={onAnalyze}
          disabled={analyze.isPending || Boolean(progress) || study.series.length === 0}
        >
          {analyze.isPending || progress ? <Spinner /> : null}
          {analyzed ? "Re-run AI analysis" : "Analyze with AI"}
        </button>

        {progress && (
          <div className="flex flex-1 items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-700">
              <div
                className="h-full bg-gradient-to-r from-brand-500 to-accent transition-all"
                style={{ width: `${progress.progress}%` }}
              />
            </div>
            <span className="w-40 text-xs capitalize text-slate-400">
              {progress.status === "failed"
                ? `Failed: ${progress.error ?? "error"}`
                : `${progress.stage.replace(/_/g, " ")} (${progress.progress}%)`}
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        <LeftSidebar study={study} segmentations={segmentations} />
        <ToolRail studyId={study.id} />
        <ViewerArea imageUrls={imageUrls} findings={findings} overlay={overlay} />
        <AiDrawer
          studyId={study.id}
          findings={findings}
          enabled={analyzed || findings.length > 0}
        />
      </div>
    </div>
  );
}
