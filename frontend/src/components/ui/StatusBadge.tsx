import { StatusPill } from "./StatusPill";

export type StatusBadgeTone = "success" | "warn" | "info" | "accent" | "emphasis" | "danger" | "neutral";

// Colour comes from the server code; the words always come from the caller's translated `label`.
export const statusToneMap: Record<string, StatusBadgeTone> = {
  draft: "neutral", pending_approval: "warn", accepted: "info", rejected: "danger",
  issued: "accent", partially_returned: "warn", returned: "success", closed_with_issue: "danger",
  checked_out: "accent", no_issue: "success", needs_fix: "warn", damaged: "danger", missing: "danger",
  available: "success", limited: "emphasis", low: "emphasis", unavailable: "neutral", reserved: "info",
  maintenance: "warn", lost: "danger", retired: "neutral", published: "success", cancelled: "neutral",
  completed: "info", registered: "success", waitlisted: "info", attended: "accent",
  pending: "warn", confirmed: "success", no_show: "danger", paid_online: "success", paid_offline: "success",
  waived: "info", canceled: "neutral", succeeded: "success", failed: "danger", idle: "success",
  running: "accent", offline: "neutral", in_progress: "accent", collected: "neutral",
  rendering: "info", active: "success", revoked: "neutral",
  changes_requested: "warn", quoted: "info", uncollected: "danger",
};

export type StatusBadgeProps = {
  status: string;
  domain?: "event" | "service";
  /** Translated words for `status`; required so a raw server code never reaches the screen. */
  label: string;
};

export function StatusBadge({ status, label, domain }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  const tone = domain === "event" && normalized === "cancelled" ? "danger"
    : domain === "service" && normalized === "completed" ? "success"
    : statusToneMap[normalized] ?? "neutral";
  return <StatusPill tone={tone} label={label} />;
}
