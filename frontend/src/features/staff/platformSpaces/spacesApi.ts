import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";

// Hand-written until the coordinator regenerates the OpenAPI snapshot (lane r2-superadmin-controls).
export type SpaceState = "active" | "read_only" | "suspended" | "archived" | "scheduled" | "importing" | "aborted";
export type CheckStatus = "ok" | "warn" | "error";
export type UsageResource = { key: string; label: string; used: number | null; limit: number | null; unit: "bytes" | "count"; percent: number | null };
export type SpaceManager = { membership_id: number; user_id: number; name: string; email: string };
export type HealthCard = {
  id: number; name: string; slug: string; public_code: string; state: SpaceState; created_at: string;
  lifecycle_state: "active" | "suspended" | "importing" | "aborted";
  archived_at: string | null;
  suspended: { at: string; reason: string; by: string | null } | null;
  read_only: { at: string; reason: string; source: "manual" | "trial_expired" | "payment_overdue"; by: string | null } | null;
  schedule: { archive_on: string | null; purge_due_at: string | null; purge_grace_days: number; note: string;
    scheduled_by: string | null; scheduled_at: string | null; reminders_sent: string[] } | null;
  usage: { managed: boolean; resources: UsageResource[] };
  usage_peak_percent: number | null;
  last_activity_at: string | null;
  backups: { last_backed_up_at: string | null; last_drill: { outcome: "passed" | "failed"; finished_at: string | null } | null };
  security: { blocked_accounts: number; locked_settings: number };
  open_issues: number;
  modules: string[];
  managers: SpaceManager[];
  plan?: { key: string; name: string; trial_ends_at: string | null } | null;
};
export type SpaceProblem = { key: string; status: CheckStatus; message: string; fix_url: string };
export type HealthDetail = HealthCard & { problems: SpaceProblem[] };
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type TransferBody = { email: string; previous_membership_id: number | null;
  previous_outcome: "keep_staff" | "revoke" | "keep_manager"; previous_roles: string[] };
export type TransferResult = { status: "transferred" | "invited"; card: HealthCard; invitation_email_status?: string };
export type ScheduleBody = { archive_on: string | null; purge_grace_days: number; note: string };

export const PAGE_SIZE = 24;
export const healthKey = ["platform-space-health"] as const;

function query(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== "") search.set(key, String(value));
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function post<T>(path: string, body: unknown = {}) {
  return staffRequest<T>(path, { method: "POST", body: JSON.stringify(body) }, "platform");
}

export const listSpaceHealth = (params: { state?: string; search?: string; page: number }) =>
  staffRequest<Page<HealthCard>>(`/admin/platform/space-health${query(params)}`, {}, "platform");
export const getSpaceHealth = (id: number) => staffRequest<HealthDetail>(`/admin/platform/space-health/${id}`, {}, "platform");

/** Every lifecycle control, keyed by the path segment after `/spaces/<id>/`. */
export type SpaceAction = "suspend" | "unsuspend" | "read-only" | "read-only/lift" | "schedule" | "schedule/cancel"
  | "archive" | "unarchive" | "purge" | "transfer-ownership";

export function runSpaceAction<T = HealthCard>(id: number, action: SpaceAction, body: unknown = {}) {
  return post<T>(`/admin/platform/spaces/${id}/${action}`, body);
}

/** One mutation per dialog; every success refreshes the health list and the open detail. */
export function useSpaceAction<T = HealthCard>(id: number, action: SpaceAction, onDone?: (result: T) => void) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: unknown) => runSpaceAction<T>(id, action, body),
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: healthKey });
      onDone?.(result);
    },
  });
}

export function percentLevel(percent: number | null): "ok" | "warning" | "limit" {
  if (percent === null) return "ok";
  return percent >= 100 ? "limit" : percent >= 80 ? "warning" : "ok";
}

export const STATE_LABELS: Record<SpaceState, string> = {
  active: "Active", read_only: "Read-only", suspended: "Suspended", archived: "Archived",
  scheduled: "Scheduled", importing: "Importing", aborted: "Import aborted",
};
