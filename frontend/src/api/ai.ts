import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/apiClient";

export type AiStatus = {
  engine: string;
  sidecar_reachable: boolean;
  sidecar_mode: string | null;
  gpu_available: boolean | null;
  vila_loaded: boolean | null;
};

export type AskResponse = {
  answer: string;
  engine: string;
  mode: string | null;
};

export function useAiStatus() {
  return useQuery({
    queryKey: ["ai", "status"],
    queryFn: async () => (await api.get<AiStatus>("/ai/status")).data,
    staleTime: 60_000,
  });
}

export function useAskStudy(studyId: string) {
  return useMutation({
    mutationFn: async (question: string) =>
      (await api.post<AskResponse>(`/studies/${studyId}/ask`, { question })).data,
  });
}
