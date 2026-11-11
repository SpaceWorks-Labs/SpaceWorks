import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Card, ErrorText, Skeleton, StatusBadge, PagePager } from "../../components/ui";
import { useBookingBroadcasts, type BookingCampaign } from "./bookingBroadcastsApi";
import { opsStatusLabel } from "./opsPresentation";

const fieldLabel = "grid gap-1 text-sm font-semibold text-ink";

function localInput(date: Date) {
  const value = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return value.toISOString().slice(0, 16);
}

export function BookingBroadcastsPanel({ makerspaceId, spaceId }: { makerspaceId: number; spaceId: number }) {
  const [page, setPage] = useState(1);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState(() => localInput(new Date(Date.now() + 7 * 86400000)));
  const [statuses, setStatuses] = useState<BookingCampaign["statuses"]>(["confirmed"]);
  const [preview, setPreview] = useState<number | null>(null);
  const { history, compose, action } = useBookingBroadcasts(makerspaceId, spaceId, page);
  const error = history.error || compose.error || action.error;
  return <section className="grid gap-4" aria-label={t`Booker broadcasts`}>
    <div><h2 className="title-panel">{t`Email upcoming bookers`}</h2>
      <p className="mt-1 text-sm text-muted">{t`One email per account with a matching future reservation. Verified email, requester settings, preferences and quiet hours apply. Accepted emails cannot be recalled.`}</p></div>
    <Card><form className="grid gap-4" onSubmit={(event) => {
      event.preventDefault();
      compose.mutate({ subject, body, statuses, window_start: start ? new Date(start).toISOString() : new Date().toISOString(), window_end: new Date(end).toISOString() },
        { onSuccess: () => { setSubject(""); setBody(""); setPage(1); } });
    }}>
      <label className={fieldLabel}>{t`Subject`}<input required maxLength={200} className="desk-input w-full min-w-0 font-normal" value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
      <label className={fieldLabel}>{t`Message`}<textarea required maxLength={10000} className="desk-input min-h-28 w-full min-w-0 font-normal" value={body} onChange={(event) => setBody(event.target.value)} /></label>
      <p className="text-xs text-muted [overflow-wrap:anywhere]">{t`Placeholders: `}{t`{{ name }}, {{ resource_name }}, {{ booking_start }}, {{ booking_end }}, {{ booking_url }}`}. Booking links require sign-in. Times refer to the earliest matching reservation.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={fieldLabel}>{t`Booking starts from (blank means now)`}<input type="datetime-local" className="desk-input w-full min-w-0 font-normal" value={start} onChange={(event) => setStart(event.target.value)} /></label>
        <label className={fieldLabel}>{t`Booking starts before`}<input required type="datetime-local" className="desk-input w-full min-w-0 font-normal" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
      </div>
      <p className="text-xs text-muted">{t`Dates use your device timezone. Choose a future window ending within 366 days.`}</p>
      <fieldset className="grid min-w-0 gap-x-4 sm:grid-cols-3"><legend className="mb-1 text-sm font-semibold text-ink">{t`Reservation states`}</legend>
        {(["confirmed", "pending"] as const).map((status) => <label key={status} className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" checked={statuses.includes(status)} onChange={(event) => setStatuses(event.target.checked ? [...statuses, status] : statuses.filter((value) => value !== status))} />{status}
        </label>)}
      </fieldset>
      <div className="flex justify-end"><button className="desk-button-primary" type="submit" disabled={compose.isPending || !statuses.length}>{compose.isPending ? t`Saving…` : t`Save draft`}</button></div>
    </form></Card>
    {history.isLoading ? <div role="status" className="grid gap-3"><span className="sr-only">{t`Loading broadcasts…`}</span><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></div> : null}
    {error ? <ErrorText message={error.message} /> : null}
    {history.data?.results.length ? <ul className="grid gap-3" aria-label={t`Sent and draft broadcasts`}>{history.data.results.map((row) => <li key={row.id} className="grid min-w-0 gap-3 rounded-2xl border border-line bg-panel p-4">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2"><p className="title-section min-w-0 break-words">{row.subject}</p><StatusBadge status={row.status} label={opsStatusLabel(row.status)} /></div>
      <p className="text-xs text-muted">{new Date(row.window_start).toLocaleString(formatLocale())} – {new Date(row.window_end).toLocaleString(formatLocale())} · {row.statuses.join(", ")}</p>
      <div className="flex flex-wrap gap-2"><button type="button" className="desk-button" aria-expanded={preview === row.id} onClick={() => setPreview(preview === row.id ? null : row.id)}>{t`Preview message`}</button>
        {row.status === "draft" ? <button type="button" className="desk-button-primary" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "queue" })}>{t`Send broadcast`}</button> : null}
        {["draft", "queued", "sending"].includes(row.status) ? <button type="button" className="desk-button-danger-outline" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "cancel" })}>{t`Cancel broadcast`}</button> : null}
      </div>
      {preview === row.id ? <div className="whitespace-pre-wrap rounded-control border border-line bg-surface p-3 text-sm text-ink [overflow-wrap:anywhere]"><p className="mb-2 text-muted">{t`Placeholders use current account and reservation data at delivery.`}</p>{row.body}</div> : null}
    </li>)}</ul> : null}
    {history.data?.count === 0 ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">{t`No broadcasts yet.`}</p> : null}
    <PagePager page={page} setPage={setPage} next={history.data?.next} />
  </section>;
}
