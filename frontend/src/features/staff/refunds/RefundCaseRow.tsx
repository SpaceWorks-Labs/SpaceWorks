import { ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { CASE_STATUS_LABELS, REASON_LABELS, caseTone, formatDuration, type RefundCase } from "./refundsApi";

/** One plain sentence explaining how the due figure was reached. */
export function policySentence(snapshot: unknown): string | null {
  if (!snapshot || typeof snapshot !== "object") return null;
  const value = snapshot as Record<string, string | number | undefined>;
  switch (value.rule) {
    case "event_cancelled_full": return "The space cancelled the event, so the full amount is owed.";
    case "staff_cancelled_full": return "Staff cancelled this booking, so the full amount is owed.";
    case "no_policy": return "No refund policy is set for this area. Decide the amount yourself.";
    case "no_policy_area": return "Refunds here have no automatic policy. Decide the amount yourself.";
    case "nothing_left": return "Nothing is left to refund on this charge.";
    case "policy": {
      const band = value.band === "full" || value.band === "never_started" ? "the full amount" : value.band === "partial"
        ? `${value.partial_percent}%` : value.band === "pro_rata" ? "the unused part of the term" : "nothing";
      const fee = Number(value.fee_applied ?? 0) > 0 ? `, minus a ${value.fee_applied} cancellation fee` : "";
      if (value.area === "membership") {
        if (value.band === "never_started") return `The renewal paid for a term that never started: the policy refunds the full amount${fee}.`;
        return `Membership term cancelled: the policy refunds ${band}${fee}.`;
      }
      const minutes = Number(value.minutes_before_start ?? 0);
      const when = minutes > 0 ? `${formatDuration(minutes)} before the start` : "after the start";
      return `Cancelled ${when}: the policy refunds ${band}${fee}.`;
    }
    default: return null;
  }
}

export function PolicySnapshotLine({ snapshot }: { snapshot: unknown }) {
  const sentence = policySentence(snapshot);
  return sentence ? <p className="text-sm text-muted">{sentence}</p> : null;
}

export function RefundCaseRow({ row, onOpen }: { row: RefundCase; onOpen?: () => void }) {
  const money = (value: string) => formatMoney(value, row.payment.currency);
  const shown = row.approved_amount ?? (Number(row.due_amount) > 0 ? row.due_amount : null);
  return <ListRow title={`${row.payment.member_name || "Member"} · ${row.payment.subject_label}`} onClick={onOpen}
    meta={<span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span>{REASON_LABELS[row.reason_code]}</span>
      <span>Paid {money(row.payment.amount)}</span>
      {row.refund?.status === "failed" ? <span className="text-danger">Provider refused the last attempt</span> : null}
      <RelativeTime date={row.created_at} />
    </span>}
    right={<div className="grid justify-items-end gap-1 text-right">
      <span className="font-display text-lg tabular-nums text-ink">{shown ? money(shown) : "Staff decide"}</span>
      <StatusPill label={CASE_STATUS_LABELS[row.status]} tone={caseTone(row.status)} />
    </div>} />;
}
