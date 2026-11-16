import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";

export type Channel = "email" | "telegram" | "whatsapp" | "sms";
export type CoverageRow = { kind: "machine_type" | "inventory" | "room"; id: number | null; label?: string };
export type Technician = {
  id: number; kind: "in_house" | "external"; person_id: number | null; name: string; email: string; phone: string;
  telegram_handle: string; channels: Channel[]; notes: string; is_archived: boolean; coverage: CoverageRow[];
  consent: Record<Channel, boolean>; opt_in_pending: boolean; pii_masked?: boolean;
};
export type TechnicianInput = Partial<Pick<Technician, "name" | "email" | "phone" | "telegram_handle" | "notes" | "channels">>
  & { person_id?: number | null; coverage?: CoverageRow[] };
export type OptInLink = { url: string; telegram_start: string; expires_at: string; emailed: boolean };

export const CHANNEL_LABELS = (): Record<Channel, string> => ({ email: t`Email`, telegram: t`Telegram`, whatsapp: t`WhatsApp`, sms: t`SMS` });
export const technicianKeys = { all: ["technicians"] as const, list: (msId: number) => ["technicians", msId] as const };

export function useTechnicians(msId: number, enabled = true) {
  return useQuery({ queryKey: technicianKeys.list(msId), enabled,
    queryFn: () => staffRequest<Technician[]>(`/admin/makerspaces/${msId}/technicians`) });
}

function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: technicianKeys.all });
}

export function useSaveTechnician(msId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: TechnicianInput }) => id
      ? staffRequest<Technician>(`/admin/technicians/${id}`, { method: "PATCH", body: JSON.stringify(body) })
      : staffRequest<Technician>(`/admin/makerspaces/${msId}/technicians`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void refresh(); },
  });
}

export function useArchiveTechnician() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => staffRequest<Technician>(`/admin/technicians/${id}`, { method: "DELETE" }),
    onSuccess: () => { void refresh(); },
  });
}

export function useOptInLink() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => staffRequest<OptInLink>(`/admin/technicians/${id}/opt-in-link`, { method: "POST" }),
    onSuccess: () => { void refresh(); },
  });
}

export function useWithdrawConsent() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, channel }: { id: number; channel: Exclude<Channel, "email"> }) =>
      staffRequest<Technician>(`/admin/technicians/${id}/consent`, { method: "POST", body: JSON.stringify({ channel }) }),
    onSuccess: () => { void refresh(); },
  });
}
