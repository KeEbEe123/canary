// TanStack Query hooks for alert rules + creating new ones.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type NewAlertRule } from "@/api/client";

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: () => api.alerts(),
    refetchInterval: 15_000,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rule: NewAlertRule) => api.createAlert(rule),
    // Re-fetch the rules list once a new rule lands.
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}
