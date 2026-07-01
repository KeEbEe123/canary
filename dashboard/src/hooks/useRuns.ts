// TanStack Query hooks for runs — the list and single-run trace.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useRuns(filters: { agent?: string; status?: string; limit?: number } = {}) {
  return useQuery({
    queryKey: ["runs", filters],
    queryFn: () => api.listRuns(filters),
  });
}

export function useRun(id: string | undefined) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => api.getRun(id as string),
    enabled: !!id,
  });
}
