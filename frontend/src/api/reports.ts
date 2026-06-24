import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/apiClient";
import { API_BASE_URL, API_PREFIX } from "@/lib/config";
import { tokenStore } from "@/lib/apiClient";
import type { Report } from "@/types";

export function useReports(studyId: string | undefined) {
  return useQuery({
    queryKey: ["reports", studyId],
    enabled: Boolean(studyId),
    queryFn: async () => (await api.get<Report[]>(`/studies/${studyId}/reports`)).data,
  });
}

export function useGenerateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (studyId: string) =>
      (await api.post<Report>(`/studies/${studyId}/reports`)).data,
    onSuccess: (_d, studyId) => qc.invalidateQueries({ queryKey: ["reports", studyId] }),
  });
}

/** Download a report artifact (auth header required, so fetch as a blob). */
export async function downloadReport(reportId: string, format: "pdf" | "docx" | "html") {
  const resp = await fetch(
    `${API_BASE_URL}${API_PREFIX}/reports/${reportId}/download?format=${format}`,
    { headers: { Authorization: `Bearer ${tokenStore.getAccess() ?? ""}` } },
  );
  if (!resp.ok) throw new Error(`Download failed (${resp.status})`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `lumira-report-${reportId}.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
