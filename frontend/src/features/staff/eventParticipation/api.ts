import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { sessionScope } from "../eventProgramme/sessionScope";

/** Lane L21a staff APIs: review stages, participation switches, attendance, crew and check-in lists. */
export type Criterion = { key: string; label: string; guidance?: string };
export type Stage = {
  id: number; event_id: number; position: number; name: string; state: "draft" | "open" | "closed"; version: number;
  reviews_per_application: number; blind: boolean; criteria: Criterion[]; guidance: string;
  opens_at: string | null; closes_at: string | null; assignment_strategy: "balanced" | "random";
  assignment_seed: string; assigned_at: string | null; frozen: boolean;
  panel: { reviewer_id: number; label: string }[]; standing: number;
};
export type Plan = {
  stage_id: number; strategy: string; seed: string; fingerprint: string; applications: number;
  pairs: { application_id: number; reviewer_id: number }[];
  deficits: { application_id: number; missing: number }[];
};
export type ProgressRow = { application_id: number; alias: string; state: string; version: number;
  reviews: number; needed: number; average: number | null };
export type Switches = { stage_advanced_email: boolean; attendance_free_on_no: boolean; crew_signup_open: boolean;
  crew_approval_required: boolean; crew_public_section: boolean };
export type AttendanceSummary = { asked: number; yes: number; no: number; pending: number; released: number;
  left_to_staff: number; next_send_at: string | null; free_on_no: boolean;
  rounds: { id: number; kind: string; state: string; recipients: number; sent: number; created_at: string }[] };
export type CrewRow = { id: number; version: number; member_id: number; name: string; crew_role: string;
  state: string; origin: string; show_publicly: boolean; registration_id: number | null; has_place: boolean };
export type Catering = { approved: number; with_needs: number; needs: { label: string; count: number }[] };
export type CheckInList = { id: number; event_id: number; name: string; kind: string; after_entry: boolean;
  addon_id: number | null; addon_name: string | null; per_person: number; archived: boolean; collected: number };
export type ListEligibility = { registration_id: number; name: string; allowed: number; used: number; reason: string | null };

export const adminBase = (eventId: number) => "/admin/events/" + eventId;

export function useStaffQuery<T>(eventId: number, suffix: string, enabled = true) {
  return useQuery({
    queryKey: ["staff-event-participation", eventId, suffix, ...sessionScope()], enabled, retry: false, staleTime: 0,
    queryFn: () => staffRequest<T>(adminBase(eventId) + suffix),
  });
}

/** A JSON command against this event; refreshes every participation query of the event on success. */
export function useStaffCommand<T = unknown>(eventId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ suffix, body, method = "POST", idempotent = false }: {
      suffix: string; body?: Record<string, unknown>; method?: "POST" | "PATCH" | "PUT"; idempotent?: boolean;
    }) => {
      const operation = crypto.randomUUID();
      const payload = idempotent ? { ...body, operation_id: operation } : body ?? {};
      return staffRequest<T>(adminBase(eventId) + suffix, {
        method, body: JSON.stringify(payload), headers: idempotent ? { "Idempotency-Key": operation } : undefined,
      });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["staff-event-participation", eventId] }),
  });
}
