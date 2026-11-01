import type {
  ConfidenceEnum,
  MachineQueueSummary,
  MemberServiceOwner,
  PublicMachineServiceStatus,
  ReasonsEnum,
  ServiceRequestEta,
} from "../../generated/api";

// The ETA contract (`ServiceRequestEtaSerializer` / `MachineQueueSummarySerializer`) comes from the
// generated OpenAPI client; these aliases keep the feature's vocabulary short.
export type { MachineQueueSummary, ServiceRequestEta };
export type EtaConfidence = ConfidenceEnum;
export type EtaReason = ReasonsEnum;
export type MachineServiceStatus = PublicMachineServiceStatus;
export type OwnerControls = MemberServiceOwner;

/** Statuses after which nothing changes: polling stops and no ETA is shown. */
export const TERMINAL_SERVICE_STATUSES = new Set(["completed", "collected", "rejected", "failed", "cancelled", "uncollected", "not_collected"]);

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
  // L12 (#141) job flow: staff statuses, then the member labels the job endpoints send.
  changes_requested: "Needs changes",
  quoted: "Quote sent",
  uncollected: "Not collected",
  submitted: "Submitted",
  needs_changes: "Needs changes",
  quote_sent: "Quote sent",
  awaiting_payment: "Awaiting payment",
  in_queue: "In the queue",
  ready_to_collect: "Ready to collect",
  not_collected: "Not collected",
};

export function serviceStatusLabel(status: string): string {
  const normalized = normalizeServiceStatus(status);
  return SERVICE_STATUS_LABELS[normalized] ?? normalized.replace(/_/g, " ");
}

export function serviceStatusTone(status: string): "success" | "info" | "warn" | "danger" | "neutral" {
  const normalized = normalizeServiceStatus(status);
  if (["completed", "collected", "ready_to_collect"].includes(normalized)) return "success";
  if (["in_progress", "accepted", "in_queue"].includes(normalized)) return "info";
  if (normalized === "failed" || normalized === "rejected") return "danger";
  if (["cancelled", "uncollected", "not_collected"].includes(normalized)) return "neutral";
  return "warn";
}

/** Same cadence as the print status page; terminal jobs stop polling entirely. */
export function statusRefetchInterval(status: string | undefined): number | false {
  const normalized = status ? normalizeServiceStatus(status) : "";
  if (!normalized || TERMINAL_SERVICE_STATUSES.has(normalized)) return false;
  return normalized === "in_progress" ? 30_000 : 90_000;
}

/** Waiting or running jobs may be cancelled (staff on the admin route, owners on the member surface). */
export const CANCELLABLE_SERVICE_STATUSES = new Set(["pending", "accepted", "in_progress"]);
