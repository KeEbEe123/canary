// TanStack Query hook for grouped error feed.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useErrors(filters: { agent?: string; tool?: string } = {}) {
  return useQuery({
    queryKey: ["errors", filters],
    queryFn: () => api.listErrors(filters),
    // Errors are the headline product surface — refresh often.
    refetchInterval: 10_000,
  });
}
