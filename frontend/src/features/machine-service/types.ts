// Mirrors the backend `ServiceRequestEtaSerializer` / `MachineQueueSummarySerializer`.
// Kept local until `generated/api.ts` is regenerated from the new OpenAPI snapshot; the
// shapes are identical, so the generated types can replace these aliases one-for-one.
export type EtaConfidence = "estimated" | "rough" | "unavailable";
export type EtaReason =
  | "awaiting_approval"
  | "missing_estimate"
  | "no_active_machine"
  | "overdue_running_job"
  | "unknown_running_job"
  | "inactive_scope"
  | "competing_scopes";

export type ServiceRequestEta = {
  calculated_at: string;
  estimated_start_at: string | null;
  estimated_finish_at: string | null;
  start_in_minutes: number | null;
  finish_in_minutes: number | null;
  confidence: EtaConfidence;
  reasons: EtaReason[];
  approved_ahead: number;
  awaiting_review_ahead: number;
  active_machine_count: number;
  missing_estimate_count: number;
};

export type MachineQueueSummary = {
  length: number;
  eta_minutes: number | null;
  estimated_clear_at: string | null;
  calculated_at: string;
  confidence: EtaConfidence;
  reasons: EtaReason[];
};

export type MachineServiceStatus = {
  public_token: string;
  status: string;
  title: string;
  machine_type_name: string;
  created_at: string;
  accepted_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  estimated_minutes: number;
  queue_position: number | null;
  queue_approved_ahead: number | null;
  queue_awaiting_review_ahead: number | null;
  eta: ServiceRequestEta | null;
};

export type OwnerControls = { request_id: number; can_cancel: boolean };

/** Statuses after which nothing changes: polling stops and no ETA is shown. */
export const TERMINAL_SERVICE_STATUSES = new Set(["completed", "collected", "rejected", "failed", "cancelled"]);

/** Printer transport still says "printing"; every surface treats it as in_progress. */
export function normalizeServiceStatus(status: string): string {
  return status === "printing" ? "in_progress" : status;
}

export const SERVICE_STATUS_LABELS: Record<string, string> = {
  pending: "Awaiting review",
  accepted: "Approved",
  in_progress: "In progress",
  completed: "Ready to collect",
  collected: "Collected",
  rejected: "Not approved",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function serviceStatusLabel(status: string): string {
  const normalized = normalizeServiceStatus(status);
  return SERVICE_STATUS_LABELS[normalized] ?? normalized.replace(/_/g, " ");
}

export function serviceStatusTone(status: string): "success" | "info" | "warn" | "danger" | "neutral" {
  const normalized = normalizeServiceStatus(status);
  if (normalized === "completed" || normalized === "collected") return "success";
  if (normalized === "in_progress" || normalized === "accepted") return "info";
  if (normalized === "failed" || normalized === "rejected") return "danger";
  if (normalized === "cancelled") return "neutral";
  return "warn";
}

/** Same cadence as the print status page; terminal jobs stop polling entirely. */
export function statusRefetchInterval(status: string | undefined): number | false {
  const normalized = status ? normalizeServiceStatus(status) : "";
  if (!normalized || TERMINAL_SERVICE_STATUSES.has(normalized)) return false;
  return normalized === "in_progress" ? 30_000 : 90_000;
}

/** Staff rows carry the shared ETA; the generated `MachineServiceRequest` type catches up on regeneration. */
export type WithEta = { eta?: ServiceRequestEta | null };

/** Waiting or running jobs may be cancelled (staff on the admin route, owners on the member surface). */
export const CANCELLABLE_SERVICE_STATUSES = new Set(["pending", "accepted", "in_progress"]);
