import { t } from "@lingui/core/macro";

import { StatusPill } from "../../../components/ui";
import { formatDateTime } from "../../../lib/format";
import type { PlanResponse, PlanResult, WindowAvailability, WindowRow } from "./eventEquipmentApi";

export function windowStatusPill(row: WindowRow) {
  if (row.status === "available") return <StatusPill tone="success" label={t`Free for the event`} />;
  if (row.status === "limited") return <StatusPill tone="warn" label={t`Limited during the event`} />;
  return <StatusPill tone="danger" label={t`Not free during the event`} />;
}

/** Exact figures only when the server sent them (inventory-view staff). */
export function windowCounts(row: WindowRow) {
  if (row.free === undefined) return "";
  const committed = row.committed ?? 0;
  return t`${row.free} free for the whole window · ${committed} committed`;
}

/** The event window the figures cover: event start to the time its loans fall due. */
export function WindowSummary({ data }: { data: WindowAvailability }) {
  const starts = formatDateTime(data.window.starts_at);
  const due = formatDateTime(data.window.return_due_at);
  const hours = data.equipment_return_hours;
  return <p className="text-sm text-muted">
    {t`Availability from ${starts} until items are due back ${due}.`}{" "}
    {hours ? t`Items are due ${hours} hours after the event ends.` : t`Items are due when the event ends.`}
  </p>;
}

/** Dry-run totals: what the plan asks for against what is free in the window. Advisory only. */
export function PlanPreview({ preview, names }: { preview: PlanResponse; names: Record<number, string> }) {
  const short = preview.totals.some((row) => row.status === "short");
  return <section className="grid gap-2" aria-label={t`Plan preview`}>
    <h5 className="font-semibold text-ink">{t`Preview`}</h5>
    <ul className="grid gap-1 text-sm">{preview.totals.map((row) => <li key={row.product_id} className="flex flex-wrap items-center gap-2">
      <span className="min-w-0 [overflow-wrap:anywhere]">{t`${names[row.product_id] ?? `#${row.product_id}`}: ${row.requested} requested`}</span>
      {row.free !== undefined ? <span className="tabular-nums text-muted">{t`${row.free} free`}</span> : null}
      <StatusPill tone={row.status === "ok" ? "success" : "warn"} label={row.status === "ok" ? t`Enough` : t`Short`} />
    </li>)}</ul>
    {short ? <p className="text-sm text-warn-ink" role="status">{t`Some items are short for the event window. Requests can still be created; inventory staff decide when they accept and issue.`}</p> : null}
  </section>;
}

function resultText(row: PlanResult) {
  if (row.outcome === "created") return t`Request #${row.request_id ?? ""} created`;
  if (row.outcome === "replayed") return t`Already created as request #${row.request_id ?? ""}`;
  if (row.code === "event_only_product") return t`Not created: an item is lent only through events.`;
  if (row.code === "not_found") return t`Not created: this registration is no longer eligible.`;
  if (row.code === "lock_busy") return t`Not created: the system was busy. Run the plan again to retry.`;
  return row.code ? t`Not created (${row.code}).` : t`Not created.`;
}

/** One line per participant, so a partial success is visible person by person. */
export function PlanResults({ results, people }: { results: PlanResult[]; people: Record<number, string> }) {
  const failed = results.filter((row) => row.outcome === "error").length;
  return <section className="grid gap-2" aria-label={t`Plan results`}>
    <h5 className="font-semibold text-ink">{t`Results`}</h5>
    <ul className="grid gap-1 text-sm">{results.map((row) => <li key={row.registration_id} className="flex flex-wrap items-center gap-2">
      <StatusPill tone={row.outcome === "error" ? "danger" : "success"} label={row.outcome === "error" ? t`Failed` : t`Done`} />
      <span className="min-w-0 [overflow-wrap:anywhere]"><strong>{people[row.registration_id] ?? t`Registration #${row.registration_id}`}</strong>: {resultText(row)}</span>
    </li>)}</ul>
    {failed ? <p className="text-sm text-danger" role="alert">{t`${failed} of ${results.length} could not be created. Running the same plan again retries only those.`}</p>
      : <p className="text-sm text-muted" role="status">{t`Requests are pending review. Inventory staff accept and issue them, one accountable person each.`}</p>}
  </section>;
}
