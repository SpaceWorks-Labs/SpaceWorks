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

/** Waiting or running jobs may be cancelled (staff on the admin route, owners on the member surface). */
export const CANCELLABLE_SERVICE_STATUSES = new Set(["pending", "accepted", "in_progress"]);
