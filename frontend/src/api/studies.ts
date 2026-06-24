import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/apiClient";
import type { Study, StudyListItem } from "@/types";

export function useStudies() {
  return useQuery({
    queryKey: ["studies"],
    queryFn: async () => (await api.get<StudyListItem[]>("/studies")).data,
  });
}

export function useStudy(studyId: string | undefined) {
  return useQuery({
    queryKey: ["study", studyId],
    enabled: Boolean(studyId),
    queryFn: async () => (await api.get<Study>(`/studies/${studyId}`)).data,
  });
}

export function useCreateStudy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Study>) =>
      (await api.post<Study>("/studies", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["studies"] }),
  });
}

export function useUploadDicom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ studyId, files }: { studyId: string; files: File[] }) => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      const { data } = await api.post(`/studies/${studyId}/upload`, form);
      return data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["study", vars.studyId] });
      qc.invalidateQueries({ queryKey: ["studies"] });
    },
  });
}

export interface DicomTag {
  tag: string;
  name: string;
  vr: string;
  value: string;
}

export function useInstanceTags(studyId: string | undefined, instanceId: string | undefined) {
  return useQuery({
    queryKey: ["tags", studyId, instanceId],
    enabled: Boolean(studyId && instanceId),
    queryFn: async () =>
      (await api.get<DicomTag[]>(`/studies/${studyId}/instances/${instanceId}/metadata`)).data,
  });
}

export function useDeleteStudy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (studyId: string) => api.delete(`/studies/${studyId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["studies"] }),
  });
}
