import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";

/** Decision 223 (k), lane L3a: induction events. Hand-typed until the client is regenerated. */
export type InductionLink = {
  id: number; event: number; certification_type: number; certification_type_name: string;
  machine_type_id: number; created_at: string;
};
export type InductionAttendee = { user_id: number; name: string; is_member: boolean; certified_type_ids: number[] };
export type InductionOverview = { links: InductionLink[]; attendees: InductionAttendee[]; can_grant: boolean };
export type InductionResult = {
  user_id: number; certification_type_id: number; status: "granted" | "already_certified" | "refused";
  grant_id?: number | null; guest?: boolean; code?: string;
};

export const inductionKeys = {
  overview: (makerspaceId: number, eventId: number) => ["event-induction", makerspaceId, eventId] as const,
};

const base = (makerspaceId: number, eventId: number) => `/admin/makerspaces/${makerspaceId}/events/${eventId}/induction`;

export function useInduction(makerspaceId: number, eventId: number, enabled: boolean) {
  return useQuery({ queryKey: inductionKeys.overview(makerspaceId, eventId), enabled, retry: false,
    queryFn: ({ signal }) => staffRequest<InductionOverview>(base(makerspaceId, eventId), { signal }) });
}

export function useInductionActions(makerspaceId: number, eventId: number) {
  const client = useQueryClient();
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: inductionKeys.overview(makerspaceId, eventId) }),
    client.invalidateQueries({ queryKey: ["certifications"] }),
  ]);
  const link = useMutation({ onSuccess: refresh, mutationFn: (certificationTypeId: number) => staffRequest<InductionLink>(
    base(makerspaceId, eventId), { method: "POST", body: JSON.stringify({ certification_type_id: certificationTypeId }) }) });
  const unlink = useMutation({ onSuccess: refresh, mutationFn: (linkId: number) => staffRequest<void>(
    `/admin/induction-links/${linkId}`, { method: "DELETE" }) });
  const grant = useMutation({ onSuccess: refresh, mutationFn: (body: { user_ids: number[]; certification_type_ids?: number[]; expires_at?: string | null }) =>
    staffRequest<{ results: InductionResult[] }>(`${base(makerspaceId, eventId)}/grant`, { method: "POST", body: JSON.stringify(body) }) });
  const revoke = useMutation({ onSuccess: refresh, mutationFn: (grantId: number) => staffRequest<void>(
    `/admin/guest-certification-grants/${grantId}/revoke`, { method: "POST", body: JSON.stringify({ notes: "" }) }) });
  return { link, unlink, grant, revoke };
}

/** Copy for one person's grant result. */
export function inductionResultText(result: InductionResult) {
  if (result.status === "granted") return result.guest ? t`Certified (guest, valid while their pass lasts)` : t`Certified`;
  if (result.status === "already_certified") return t`Already certified`;
  switch (result.code) {
    case "guest_pass_required": return t`Not certified: not a member and holds no active guest pass`;
    default: return result.code ? t`Not certified (${result.code})` : t`Not certified (refused)`;
  }
}

/** Copy for refusals of the whole request. */
export function inductionErrorText(code: string | undefined) {
  if (code === "event_not_started") return t`Certifications can be granted once the event has started.`;
  return "";
}
