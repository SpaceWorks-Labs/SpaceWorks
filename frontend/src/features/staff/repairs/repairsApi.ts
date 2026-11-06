import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { uploadToStorage, type PrintUpload } from "../../printing/publicApi";

export type IssueArea = "machines" | "inventory" | "rooms";
export type IssueState = "reported" | "triaged" | "assigned" | "in_progress" | "fixed" | "closed" | "rejected";
export type SubjectType = "machine" | "inventory_product" | "inventory_asset" | "bookable_space";
export type Assignee = { id: number; contact_id: number | null; person_id: number | null; name: string };
export type Issue = {
  id: number; area: IssueArea; subject_type: SubjectType; subject_id: number; subject_label: string;
  source: "loan" | "booking" | "machine_job" | "staff"; title: string; state: IssueState;
  priority: "low" | "normal" | "high" | "urgent"; quote_state: "none" | "pending" | "approved" | "declined";
  reporter_name: string; assignees: Assignee[]; work_order_id: number | null; created_at: string; updated_at: string;
  fixed_at: string | null; closed_at: string | null;
};
export type IssueEvent = { id: number; kind: string; actor_name: string; contact_name: string; note: string;
  occurred_on: string | null; amount: string | null; currency: string; created_at: string };
export type IssueDetail = Issue & {
  description: string; resolution: string; reporter_email: string; quote_amount: string | null; quote_currency: string;
  quote_note: string; quote_contact_id: number | null; payout_entry_id: number | null; reporter_notified_at: string | null;
  events: IssueEvent[]; photos: { id: number; stage: string; url: string; created_at: string }[];
  dispatches: { id: number; contact_id: number; contact_name: string; channel: string; status: "delivered" | "failed";
    failure_code: string; sent_at: string }[];
  parts: { id: number; kind: "used" | "needed"; name: string; quantity: number; to_buy_item_id: number | null }[];
  viewer_role: "manager" | "technician"; default_contact_ids: number[];
};
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const STATE_LABELS: Record<IssueState, string> = {
  reported: t`Reported`, triaged: t`Triaged`, assigned: t`Assigned`, in_progress: t`In progress`, fixed: t`Fixed`,
  closed: t`Closed`, rejected: t`Rejected`,
};
export const AREA_LABELS: Record<IssueArea, string> = { machines: t`Machine`, inventory: t`Item`, rooms: t`Room` };
export const OPEN_STATES: IssueState[] = ["reported", "triaged", "assigned", "in_progress"];
export function stateTone(state: IssueState) {
  return state === "reported" ? "warn" as const : state === "in_progress" ? "accent" as const
    : state === "fixed" || state === "closed" ? "success" as const : state === "rejected" ? "danger" as const : "neutral" as const;
}

export const repairKeys = {
  all: ["repairs"] as const,
  list: (msId: number, query: string) => ["repairs", "issues", msId, query] as const,
  mine: (msId: number, page: number) => ["repairs", "mine", msId, page] as const,
  detail: (id: number) => ["repairs", "issue", id] as const,
};

export function useIssues(msId: number, query: string, enabled = true) {
  return useQuery({ queryKey: repairKeys.list(msId, query), enabled,
    queryFn: () => staffRequest<Page<Issue>>(`/admin/makerspaces/${msId}/issues?${query}`) });
}

export function useMyJobs(msId: number, page = 1, enabled = true) {
  return useQuery({ queryKey: repairKeys.mine(msId, page), enabled,
    queryFn: () => staffRequest<Page<Issue>>(`/admin/makerspaces/${msId}/my-jobs?page=${page}`) });
}

export function useIssue(id: number | null) {
  return useQuery({ queryKey: repairKeys.detail(id ?? 0), enabled: !!id,
    queryFn: () => staffRequest<IssueDetail>(`/admin/issues/${id}`) });
}

export type IssueStep = "triage" | "reject" | "assign" | "unassign" | "dispatch" | "start" | "work-log" | "parts"
  | "quote" | "approve" | "payout" | "fix" | "close";

/** Every lifecycle step answers the refreshed issue; queues and stock views refresh too. */
export function useIssueStep(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ step, body = {} }: { step: IssueStep; body?: Record<string, unknown> }) =>
      staffRequest<IssueDetail>(`/admin/issues/${id}/${step}`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (issue) => {
      client.setQueryData(repairKeys.detail(id), issue);
      void client.invalidateQueries({ queryKey: repairKeys.all });
      void client.invalidateQueries({ queryKey: ["work-orders"] });
      void client.invalidateQueries({ queryKey: ["procurement"] });
    },
  });
}

export function useOpenIssue(msId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { subject_type: SubjectType; subject_id: number; title: string; description?: string; priority?: string }) =>
      staffRequest<IssueDetail>(`/admin/makerspaces/${msId}/issues`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: repairKeys.all }); },
  });
}

/** Presign a private photo (staging key), send the bytes, and return the token the step attaches. */
export async function uploadIssuePhoto(msId: number, file: File) {
  const staged = await staffRequest<{ photo_token: string; upload: PrintUpload; max_bytes: number }>(
    `/admin/makerspaces/${msId}/issues/photos`, { method: "POST", body: JSON.stringify({ content_type: file.type }) });
  if (file.size > staged.max_bytes) throw new Error(t`${file.name} is larger than ${Math.floor(staged.max_bytes / 1_048_576)} MB.`);
  await uploadToStorage({ ...staged.upload, fields: staged.upload.fields ?? {} }, file);
  return staged.photo_token;
}

export type ServiceStateBody = { subject_type: SubjectType; subject_id: number; in_service: boolean; reason?: string;
  expected_back_at?: string | null; quantity?: number | null; mode?: "block" | "warn"; issue_id?: number | null };
export type ServiceStateResult = { state: string; outage_id: number | null;
  affected_bookings: { id: number; starts_at: string; ends_at: string; status: string }[] };

export function useServiceState(msId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ServiceStateBody) => staffRequest<ServiceStateResult>(`/admin/makerspaces/${msId}/service-state`,
      { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: repairKeys.all }),
      client.invalidateQueries({ queryKey: ["machines"] }), client.invalidateQueries({ queryKey: ["room-outages"] })]),
  });
}
