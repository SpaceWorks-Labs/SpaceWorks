import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../lib/api";

export type DowntimePeriod = { id: number; kind: "maintenance" | "offline"; reason: string; expected_back_at: string | null; started_at: string; ended_at: string | null };
export type Downtime = { summary: { days: number; uptime_percent: number; periods: number; mean_hours_to_repair: number | null }; periods: DowntimePeriod[] };
export type Lockout = { locked: boolean; schedules: { id: number; description: string; next_due: string }[] };

export const downtimeKeys = {
  downtime: (machineId: number) => ["machine-downtime", machineId] as const,
  lockout: (machineId: number) => ["machine-lockout", machineId] as const,
};

export function useMachineDowntime(machineId: number, enabled = true) {
  return useQuery({ queryKey: downtimeKeys.downtime(machineId), enabled,
    queryFn: () => staffRequest<Downtime>(`/admin/machines/${machineId}/downtime`) });
}

export function useUpdateDowntime(machineId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { reason?: string; expected_back_at?: string | null }) =>
      staffRequest<Downtime>(`/admin/machines/${machineId}/downtime`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: data => client.setQueryData(downtimeKeys.downtime(machineId), data),
  });
}

export function useMachineLockout(machineId: number, enabled = true) {
  return useQuery({ queryKey: downtimeKeys.lockout(machineId), enabled, retry: false,
    queryFn: () => staffRequest<Lockout>(`/admin/machines/${machineId}/lockout`) });
}

/** `datetime-local` input value for an ISO instant, in the viewer's own zone. */
export function localInputValue(iso: string | null | undefined) {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
