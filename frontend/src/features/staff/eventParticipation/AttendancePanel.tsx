import { formatLocale } from "../../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { Card, ErrorText, Metric } from "../../../components/ui";
import { useStaffCommand, useStaffQuery, type AttendanceSummary, type Switches } from "./api";

/**
 * "Are you still coming?" (X43). Staff send it from here; nothing sends it automatically, and
 * the server refuses a second email within 12 hours. With "free the place on No" on, a No on a
 * free place releases it to the waitlist; a paid place is cancelled under the refund policy and
 * any refund waits for staff approval. Seats from multi-ticket orders are left to staff.
 */
export function AttendancePanel({ eventId, canConfigure }: { eventId: number; canConfigure: boolean }) {
  const summary = useStaffQuery<AttendanceSummary>(eventId, "/attendance-confirmation/");
  const switches = useStaffQuery<Switches>(eventId, "/participation-settings/");
  const send = useStaffCommand<AttendanceSummary>(eventId), save = useStaffCommand<Switches>(eventId);
  const data = summary.data, nextAt = data?.next_send_at ? new Date(data.next_send_at) : null;
  const waiting = nextAt !== null && nextAt.getTime() > Date.now();
  const error = summary.error ?? send.error ?? save.error;
  return <section className="grid gap-4" aria-labelledby="attendance-heading">
    <header className="grid gap-1">
      <h3 id="attendance-heading" className="text-lg font-semibold text-ink">{t`Are you still coming?`}</h3>
      <p className="text-sm text-muted">{t`Ask registered people to confirm. Replies show in the guest list, at the desk and in the export.`}</p>
    </header>
    {error ? <ErrorText message={error.message} /> : null}
    {data ? <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Metric label={t`Asked`} value={data.asked} /><Metric label={t`Still coming`} value={data.yes} />
      <Metric label={t`Not coming`} value={data.no} /><Metric label={t`No answer yet`} value={data.pending} />
    </div> : <p role="status">{t`Loading replies…`}</p>}
    {data && (data.released || data.left_to_staff) ? <p className="text-sm text-muted">
      {data.left_to_staff
        ? plural(data.released, { one: `# place released; ${data.left_to_staff} from group orders left for you to handle.`, other: `# places released; ${data.left_to_staff} from group orders left for you to handle.` })
        : plural(data.released, { one: "# place released.", other: "# places released." })}</p> : null}
    <Card><div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button" disabled={send.isPending || waiting}
        onClick={() => send.mutate({ suffix: "/attendance-confirmation/", body: { kind: "confirmation" } })}>{t`Ask everyone not yet asked`}</button>
      <button type="button" className="desk-button" disabled={send.isPending || waiting || !data?.asked}
        onClick={() => send.mutate({ suffix: "/attendance-confirmation/", body: { kind: "reminder" } })}>{t`Remind people who have not answered`}</button>
      {waiting ? <p className="text-sm text-muted" role="status">{t`The next email can go out after ${nextAt!.toLocaleString(formatLocale())}.`}</p> : null}
    </div></Card>
    {canConfigure && switches.data ? <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={switches.data.attendance_free_on_no} disabled={save.isPending}
        onChange={e => save.mutate({ suffix: "/participation-settings/", method: "PATCH", body: { attendance_free_on_no: e.target.checked } })} />
      {t`Free the place when someone answers No (paid places open a refund case for you to approve)`}</label> : null}
  </section>;
}
