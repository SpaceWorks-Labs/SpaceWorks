import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";

export type EmbedPolicy = { enabled: boolean; allowed_origins: string[]; embed_path?: string };
export type ReportSwitch = {
  key: "reports.event_pdf" | "reports.event_exports"; label: string; description: string;
  enabled: boolean; effective: boolean; editable: boolean; locked: boolean; code: string | null;
};
export type HostOption = { id: number; name: string; slug: string };

const embedPath = (space: number) => `/admin/makerspaces/${space}/events/embed-policy/`;
const switchesPath = (space: number) => `/admin/makerspaces/${space}/events/report-switches/`;

export function useEmbedPolicy(space: number) {
  return useQuery({ queryKey: ["event-embed-policy", space], retry: false, staleTime: 0,
    queryFn: () => staffRequest<EmbedPolicy>(embedPath(space)) });
}

export function useSaveEmbedPolicy(space: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ enabled, allowed_origins }: EmbedPolicy) => staffRequest<EmbedPolicy>(embedPath(space),
      { method: "PUT", body: JSON.stringify({ enabled, allowed_origins }) }),
    onSuccess: data => client.setQueryData(["event-embed-policy", space], data),
  });
}

export function useReportSwitches(space: number) {
  return useQuery({ queryKey: ["event-report-switches", space], retry: false, staleTime: 0,
    queryFn: () => staffRequest<{ switches: ReportSwitch[] }>(switchesPath(space)) });
}

export function useSaveReportSwitch(space: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (switches: Record<string, boolean>) => staffRequest<{ switches: ReportSwitch[] }>(switchesPath(space),
      { method: "PATCH", body: JSON.stringify({ switches }) }),
    onSuccess: data => {
      client.setQueryData(["event-report-switches", space], data);
      // The switches live on the makerspace: its feature list, domain settings and authority views change too.
      void client.invalidateQueries({ queryKey: ["domain-settings", space] });
    },
  });
}

export function useHostOptions(enabled = true) {
  return useQuery({ queryKey: ["event-host-options"], enabled, retry: false, staleTime: 60_000,
    queryFn: () => staffRequest<HostOption[]>("/admin/events/host-options/") });
}
