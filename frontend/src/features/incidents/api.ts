import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { memberRequest, staffRequest, StructuredApiError } from "../../lib/api";

/** Decision 223 (k): the incident register (`safety.incidents`). Hand-typed from
 *  backend/apps/maintenance/incidents/serializers.py; every route 404s while the switch is off. */
export type IncidentKind = "incident" | "near_miss";
export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "reported" | "triaged" | "in_progress" | "resolved" | "closed";
export type IncidentArea = "machines" | "lending" | "events" | "bookings" | "other";

export type IncidentAction = {
  id: number; description: string; assignee: number | null; assignee_name: string; due_date: string | null;
  done_at: string | null; created_at: string;
};
export type Incident = {
  id: number; makerspace: number; kind: IncidentKind; severity: IncidentSeverity; status: IncidentStatus; area: IncidentArea;
  title: string; description: string; location: string; occurred_at: string; reporter: number | null; reporter_name: string;
  involved_user: number | null; involved_name: string; involved_note: string; sponsor_user: number | null;
  machine: number | null; room: number | null; event: number | null; loan: number | null; booking: number | null;
  repair_issue: number | null; guest_pass: number | null; triaged_by: number | null; resolution_note: string;
  closed_at: string | null; created_at: string; updated_at: string; actions: IncidentAction[];
};
export type MemberIncident = Pick<Incident, "id" | "kind" | "severity" | "status" | "area" | "title" | "description"
  | "location" | "occurred_at" | "machine" | "room" | "event" | "loan" | "booking" | "created_at">;
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
/** `admin/incidents/{id}/assignees`: active staff who could triage this incident themselves (0.12.0). */
export type IncidentAssignee = { id: number; display_name: string };

/** Fields both forms send; the staff form adds the area and the involved person. */
export type IncidentReport = {
  kind: IncidentKind; severity: IncidentSeverity; title: string; description?: string; location?: string;
  occurred_at?: string; machine_id?: number | null; room_id?: number | null; event_id?: number | null;
  loan_id?: number | null; booking_id?: number | null;
};
export type StaffIncidentReport = IncidentReport & { area?: IncidentArea; involved_user_id?: number | null; involved_note?: string };
export type IncidentPatch = Partial<Pick<Incident, "status" | "severity" | "area" | "resolution_note">>;
export type IncidentFilters = { status: string; severity: string; area: string; kind: string };

export const KIND_LABELS: Record<IncidentKind, string> = { incident: t`Incident`, near_miss: t`Near miss` };
export const SEVERITY_LABELS: Record<IncidentSeverity, string> = { low: t`Low`, medium: t`Medium`, high: t`High`, critical: t`Critical` };
export const STATUS_LABELS: Record<IncidentStatus, string> = {
  reported: t`Reported`, triaged: t`Triaged`, in_progress: t`In progress`, resolved: t`Resolved`, closed: t`Closed`,
};
export const AREA_LABELS: Record<IncidentArea, string> = {
  machines: t`Machines`, lending: t`Inventory`, events: t`Events`, bookings: t`Rooms and bookings`, other: t`Other`,
};
export const options = <K extends string>(labels: Record<K, string>) =>
  (Object.keys(labels) as K[]).map(value => ({ value, label: labels[value] }));

export function statusTone(status: IncidentStatus) {
  return status === "reported" ? "warn" as const : status === "resolved" || status === "closed" ? "success" as const : "accent" as const;
}
export function severityTone(severity: IncidentSeverity) {
  return severity === "critical" || severity === "high" ? "danger" as const : severity === "medium" ? "warn" as const : "neutral" as const;
}

/** Friendly copy for the refusals these routes send; the server's own sentence otherwise. */
export function incidentErrorMessage(error: unknown): string {
  if (error instanceof StructuredApiError) {
    if (error.code === "feature_disabled") return t`The incident register is switched off for this space.`;
    if (error.status === 404) return t`That incident, or a record it links to, could not be found.`;
    if (error.status === 403 && !error.detail) return t`You can't change this incident.`;
    if (error.status === 429) return t`Too many reports at once. Wait a moment and try again.`;
  }
  return error instanceof Error && error.message ? error.message : t`Something went wrong. Try again.`;
}

export const incidentKeys = {
  all: ["incidents"] as const,
  list: (msId: number, filters: IncidentFilters, page: number) => ["incidents", "staff", msId, filters, page] as const,
  detail: (id: number) => ["incidents", "detail", id] as const,
  assignees: (id: number) => ["incidents", "assignees", id] as const,
  mine: (msId: number, page: number) => ["incidents", "member", msId, page] as const,
};

const json = (body: unknown) => JSON.stringify(body);

/** Records the register can be narrowed to from a cross-link (`?machine=12`); batch 1 serves the filters. */
export const SUBJECT_FILTERS = ["machine", "event", "booking", "room", "loan", "product", "person"] as const;
export type IncidentSubjectFilter = { key: (typeof SUBJECT_FILTERS)[number]; id: number } | null;

export function useIncidents(msId: number, filters: IncidentFilters, page: number, subject: IncidentSubjectFilter = null) {
  const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
  if (subject) params.set(subject.key, String(subject.id));
  params.set("page", String(page));
  return useQuery({ queryKey: [...incidentKeys.list(msId, filters, page), subject?.key ?? "", subject?.id ?? 0], retry: false,
    queryFn: () => staffRequest<Page<Incident>>(`/admin/makerspaces/${msId}/incidents?${params}`) });
}

export function useIncident(id: number) {
  return useQuery({ queryKey: incidentKeys.detail(id), retry: false,
    queryFn: () => staffRequest<Incident>(`/admin/incidents/${id}`) });
}

/** Who a follow-up may be assigned to; refreshed with the incident, since a new area changes the set. */
export function useIncidentAssignees(id: number) {
  return useQuery({ queryKey: incidentKeys.assignees(id), retry: false,
    queryFn: ({ signal }) => staffRequest<{ results: IncidentAssignee[] }>(`/admin/incidents/${id}/assignees`, { signal }) });
}

export function useRecordIncident(msId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: StaffIncidentReport) =>
      staffRequest<Incident>(`/admin/makerspaces/${msId}/incidents`, { method: "POST", body: json(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: incidentKeys.all }),
  });
}

/** Triage, a new follow-up action, or a done toggle: each refreshes the incident and the register. */
export function useIncidentChange(id: number) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: incidentKeys.all });
  const triage = useMutation({
    mutationFn: (body: IncidentPatch) => staffRequest<Incident>(`/admin/incidents/${id}`, { method: "PATCH", body: json(body) }),
    onSuccess: incident => { client.setQueryData(incidentKeys.detail(id), incident); return refresh(); },
  });
  const addAction = useMutation({
    mutationFn: (body: { description: string; assignee_id?: number | null; due_date?: string | null }) =>
      staffRequest<IncidentAction>(`/admin/incidents/${id}/actions`, { method: "POST", body: json(body) }),
    onSuccess: refresh,
  });
  const toggleAction = useMutation({
    mutationFn: ({ actionId, done }: { actionId: number; done: boolean }) =>
      staffRequest<IncidentAction>(`/admin/incident-actions/${actionId}`, { method: "PATCH", body: json({ done }) }),
    onSuccess: refresh,
  });
  return { triage, addAction, toggleAction };
}

export function useMyIncidents(msId: number, page: number) {
  return useQuery({ queryKey: incidentKeys.mine(msId, page), retry: false,
    queryFn: () => memberRequest<Page<MemberIncident>>(`/member/makerspaces/${msId}/incidents?page=${page}`) });
}

export function useReportIncident(msId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: IncidentReport) =>
      memberRequest<MemberIncident>(`/member/makerspaces/${msId}/incidents`, { method: "POST", body: json(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["incidents", "member", msId] }),
  });
}
