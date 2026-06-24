import { useViewerStore } from "@/store/viewerStore";

const PREFIX = "ai-autocontour-session:";

export function loadViewerSession(studyId: string) {
  try {
    const raw = localStorage.getItem(`${PREFIX}${studyId}`);
    if (!raw) return;
    const data = JSON.parse(raw) as Record<string, unknown>;
    useViewerStore.getState().hydrateSession(data as never);
  } catch {
    /* noop */
  }
}

export function saveViewerSession(studyId: string) {
  try {
    const snap = useViewerStore.getState().sessionSnapshot();
    localStorage.setItem(`${PREFIX}${studyId}`, JSON.stringify(snap));
  } catch {
    /* noop */
  }
}
