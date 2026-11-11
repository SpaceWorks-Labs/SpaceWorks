import { t } from "@lingui/core/macro";
import { formatLocale } from "../../lib/format";
import { serviceStatusLabel, serviceStatusTone, type ServiceRequestEta } from "../machine-service/types";

/** One machine type taking job requests (GET /public/{slug}/machine-jobs/types). */
export type JobType = {
  queue_id: number; name: string; machine_type_id: number; machine_type_name: string; machine_type_slug: string;
  is_printer: boolean; file_groups: string[]; accepted_extensions: string[];
  quotes: "auto" | "off" | "above" | "always"; prepay: boolean; runs_unattended: boolean; max_open_jobs: number | null;
};

export type JobQuote = { total: string; currency: string; lines: { label: string; net: string }[]; digest: string };

export type JobLabel = "submitted" | "needs_changes" | "quote_sent" | "awaiting_payment" | "in_queue" | "in_progress"
  | "ready_to_collect" | "collected" | "not_collected" | "rejected" | "failed" | "cancelled";

/** The member's own job (GET /member/machine-jobs[/{id}]). */
export type MemberJob = {
  id: number; public_token: string; makerspace_id: number; queue_id: number | null; title: string; status: string;
  label: JobLabel | string; can_cancel: boolean;
  machine_type_name: string; machine_name: string; position: number | null; eta: ServiceRequestEta | null;
  timeline: { step: string; at: string }[]; changes_message: string; quote: JobQuote | null;
  quote_expires_at: string | null; awaiting_payment: boolean; reason: string; fail_code: string;
  failure_outcome: "requeued" | "charged" | "free" | "staff_decide" | ""; pickup_code: string; pickup_location: string;
  copies: number; needed_by: string | null; created_at: string;
};

export type JobSubmitBody = {
  queue_id: number; title: string; description?: string; source_link?: string; file_ids: number[]; copies: number;
  needed_by?: string; own_material: boolean; material_note?: string;
  capability_payload?: { schema_version: number; values: Record<string, string | number | boolean> };
  material?: string; color?: string; consumable_pool_id?: number | null; estimated_filament_grams?: string | null;
  preferred_settings?: string;
  acknowledgements: { pickup_policy: boolean; failure_policy: boolean; own_content: boolean };
};

/** The member label in words, from the one status vocabulary every machine-service surface shares. */
export function jobLabel(label: string) {
  return { text: serviceStatusLabel(label), tone: serviceStatusTone(label) };
}

export const TIMELINE_STEPS: Record<string, string> = {
  submitted: t`Submitted`, needs_changes: t`Changes requested`, quote_sent: t`Quote sent`, quote_approved: t`Quote approved`,
  in_queue: t`Joined the queue`, in_progress: t`Started`, ready_to_collect: t`Ready to collect`, collected: t`Collected`,
  not_collected: t`Not collected`, failed: t`Failed`, cancelled: t`Cancelled`,
};

/** Labels that end the job: no polling, no cancel. */
export const FINISHED_LABELS = new Set(["collected", "not_collected", "rejected", "failed", "cancelled"]);

export function jobRefetchInterval(job: MemberJob | undefined): number | false {
  if (!job || FINISHED_LABELS.has(job.label)) return false;
  return job.label === "in_progress" || job.label === "in_queue" ? 30_000 : 90_000;
}

const FAIL_CODES = (): Record<string, string> => ({
  adhesion: t`the print came off the bed`, nozzle_jam: t`nozzle jam`, material_ran_out: t`material ran out`,
  machine_fault: t`machine fault`, power_cut: t`power cut`, operator_error: t`operator error`, file_problem: t`a problem with the file`,
  material_defect: t`faulty material`, other: "",
});
const OUTCOMES = (): Record<string, string> => ({
  requeued: t`re-queued at the front, no charge`, free: t`no charge`, charged: t`charged as agreed`,
  staff_decide: t`staff will tell you what happens next`,
});

/** "Failed: nozzle jam — re-queued at the front, no charge". */
export function failureText(job: Pick<MemberJob, "fail_code" | "failure_outcome" | "reason">) {
  const cause = FAIL_CODES()[job.fail_code] ?? job.fail_code.replace(/_/g, " ");
  const outcome = OUTCOMES()[job.failure_outcome] ?? "";
  const head = cause ? `Failed: ${cause}` : "Failed";
  return outcome ? `${head} — ${outcome}` : head;
}

const DAY = 24 * 60 * 60 * 1000;
function clock(date: Date) {
  return new Intl.DateTimeFormat(formatLocale(), { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

/** Within a day: "in about 2 h 10 min". Beyond: a day and a clock time, "Thu, about 14:00". */
export function etaWhen(iso: string, now: Date, minutesLabel: (minutes: number) => string) {
  const date = new Date(iso);
  const ms = date.getTime() - now.getTime();
  if (ms <= 0) return "now";
  if (ms <= DAY) return `in ${minutesLabel(Math.round(ms / 60_000))}`;
  const day = new Intl.DateTimeFormat(formatLocale(), ms > 6 * DAY
    ? { weekday: "short", day: "numeric", month: "short" } : { weekday: "short" }).format(date);
  return `${day}, about ${clock(date)}`;
}
