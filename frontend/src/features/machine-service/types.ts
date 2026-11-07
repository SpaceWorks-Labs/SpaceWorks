import { t } from "@lingui/core/macro";
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
  pending: t`Awaiting review`,
  accepted: t`Approved`,
  in_progress: t`In progress`,
  completed: t`Ready to collect`,
  collected: t`Collected`,
  rejected: t`Not approved`,
  failed: t`Failed`,
  cancelled: t`Cancelled`,
  // L12 (#141) job flow: staff statuses, then the member labels the job endpoints send.
  changes_requested: t`Needs changes`,
  quoted: t`Quote sent`,
  uncollected: t`Not collected`,
  submitted: t`Submitted`,
  needs_changes: t`Needs changes`,
  quote_sent: t`Quote sent`,
  awaiting_payment: t`Awaiting payment`,
  in_queue: t`In the queue`,
  ready_to_collect: t`Ready to collect`,
  not_collected: t`Not collected`,
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
