// TanStack Query hook for the aggregate stats overview.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useStats(days = 7) {
  return useQuery({
    queryKey: ["stats", days],
    queryFn: () => api.stats(days),
    refetchInterval: 15_000,
  });
}
