import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/apiClient";
import type { Annotation, Finding, Job, Segmentation, StudyOverlay } from "@/types";

export function useAnalyze() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (studyId: string) =>
      (await api.post<Job>(`/studies/${studyId}/analyze`)).data,
    onSuccess: (_d, studyId) => {
      qc.invalidateQueries({ queryKey: ["study", studyId] });
    },
  });
}

export function useFindings(studyId: string | undefined) {
  return useQuery({
    queryKey: ["findings", studyId],
    enabled: Boolean(studyId),
    queryFn: async () => (await api.get<Finding[]>(`/studies/${studyId}/findings`)).data,
  });
}

export function useSegmentations(studyId: string | undefined) {
  return useQuery({
    queryKey: ["segmentations", studyId],
    enabled: Boolean(studyId),
    queryFn: async () =>
      (await api.get<Segmentation[]>(`/studies/${studyId}/segmentations`)).data,
  });
}

export function useStudyOverlay(studyId: string | undefined) {
  return useQuery({
    queryKey: ["overlay", studyId],
    enabled: Boolean(studyId),
    queryFn: async () => (await api.get<StudyOverlay>(`/studies/${studyId}/overlay`)).data,
  });
}

export function useAnnotations(studyId: string | undefined) {
  return useQuery({
    queryKey: ["annotations", studyId],
    enabled: Boolean(studyId),
    queryFn: async () =>
      (await api.get<Annotation[]>(`/studies/${studyId}/annotations`)).data,
  });
}

export function useUpdateAnnotation(studyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, text }: { id: string; text: string }) =>
      (await api.put<Annotation>(`/annotations/${id}`, { text })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["annotations", studyId] }),
  });
}

export function useDeleteAnnotation(studyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/annotations/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["annotations", studyId] }),
  });
}
