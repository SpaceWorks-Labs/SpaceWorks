import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
export function LiveTicketState({ status, attendedAt }: { status: string; attendedAt?: string | null }) {
  const attended = status === "attended";
  return <div className={`rounded-control border border-dashed p-3 ${attended ? "border-success-ink bg-success-soft text-success-ink" : "border-line text-muted"}`}
    role="status" aria-live="polite" data-ticket-state={attended ? "torn" : "intact"}>
    <p className="text-sm font-semibold">{attended ? t`Checked in` : t`Ready for event check-in`}</p>
    {attended && attendedAt ? <time className="text-sm" dateTime={attendedAt}>{new Date(attendedAt).toLocaleString(formatLocale())}</time> : null}
    <p className="text-xs">{attended ? t`Your badge can still identify you at this event. Attendance is already recorded.` : t`The desk confirms attendance after scanning. This ticket refreshes automatically.`}</p>
  </div>;
}
