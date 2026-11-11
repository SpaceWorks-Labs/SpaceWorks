import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Modal, SegmentedControl } from "../../../components/ui";
import { useRoomOutageImpact, useServiceState, type IssueDetail, type ServiceStateResult } from "./repairsApi";

function iso(value: string) {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date.toISOString() : null;
}

/** Before saving: the bookings and linked events the outage would meet (read-only; nothing is cancelled). */
export function OutageImpact({ makerspaceId, roomId, back }: { makerspaceId: number; roomId: number; back: string }) {
  const impact = useRoomOutageImpact(makerspaceId, roomId, iso(back));
  if (impact.isPending) return <p className="text-sm text-muted" role="status">{t`Checking bookings and events in this time…`}</p>;
  if (impact.isError) return null;
  const { booking_count: count, events, other_event_bookings: other } = impact.data;
  return <section className="grid gap-1 rounded-md border border-line p-2 text-sm" aria-label={t`Outage impact`}>
    {impact.data.already_out_of_service ? <p role="alert">{t`This room is already out of service.`}</p> : null}
    <p>{count ? t`${count} pending or confirmed bookings fall in this time.` : t`No bookings fall in this time.`}</p>
    {impact.data.bookings.map(row => <p key={row.id}>#{row.id} · {new Date(row.starts_at).toLocaleString(formatLocale())} ({row.status})</p>)}
    {events.length ? <><p className="font-semibold">{t`Events using this room`}</p>
      <ul className="grid gap-1">{events.map(row => <li key={row.event_id}>{row.title}</li>)}</ul></> : null}
    {other ? <p>{t`${other} more bookings hold the room for events you cannot see.`}</p> : null}
    {count ? <p className="text-muted">{t`Nothing is cancelled. Bookers and event organizers are told; staff decide on each booking.`}</p> : null}
  </section>;
}

/**
 * Take the issue's subject out of service, or back in (#93, C-6b). A room either blocks new
 * bookings (the default) or only warns; bookings already inside the outage are listed for
 * staff to cancel (the member is owed the full amount) or keep, from the Bookings tab.
 */
export function ServiceStateDialog({ issue, makerspaceId, onClose }: { issue: IssueDetail; makerspaceId: number; onClose: () => void }) {
  const change = useServiceState(makerspaceId);
  const [direction, setDirection] = useState("out");
  const [reason, setReason] = useState(issue.title);
  const [back, setBack] = useState("");
  const [mode, setMode] = useState<"block" | "warn">("block");
  const [quantity, setQuantity] = useState("1");
  const [result, setResult] = useState<ServiceStateResult | null>(null);
  const room = issue.subject_type === "bookable_space";
  const counted = issue.subject_type === "inventory_product";
  return <Modal open title={t`In or out of service`} onClose={onClose}>
    {result ? <div className="grid gap-3">
      <p>{t`Done: ${issue.subject_label} is now ${result.state.replace(/[_:]/g, " ")}.`}</p>
      {result.affected_bookings.length ? <div className="grid gap-1"><p className="font-semibold">{t`Bookings inside the outage`}</p>
        {result.affected_bookings.map(row => <p key={row.id} className="text-sm">#{row.id} · {new Date(row.starts_at).toLocaleString(formatLocale())} ({row.status})</p>)}
        <p className="text-sm text-muted">{t`Their bookers were emailed. Cancel or keep each one from the Bookings tab.`}</p></div> : null}
      <div className="flex justify-end"><button type="button" className="desk-button-primary" onClick={onClose}>{t`Done`}</button></div>
    </div> : <form className="grid gap-3" onSubmit={event => {
      event.preventDefault();
      change.mutate({ subject_type: issue.subject_type, subject_id: issue.subject_id, in_service: direction === "in", issue_id: issue.id,
        reason: reason.trim(), expected_back_at: back ? new Date(back).toISOString() : null, mode,
        quantity: counted ? Number(quantity) : null }, { onSuccess: setResult });
    }}>
      <SegmentedControl label={t`Direction`} value={direction} onChange={setDirection} fullWidth
        options={[{ value: "out", label: t`Out of service` }, { value: "in", label: t`Back in service` }]} />
      {direction === "out" ? <>
        <label className="eyebrow grid gap-1">{t`Reason`}<input className="desk-input" maxLength={300} value={reason} onChange={event => setReason(event.target.value)} /></label>
        <label className="eyebrow grid gap-1">{t`Expected back (optional)`}<input className="desk-input w-full min-w-0" type="datetime-local" value={back}
          onChange={event => setBack(event.target.value)} /></label>
        {room ? <SegmentedControl label={t`New bookings`} value={mode} onChange={value => setMode(value as "block" | "warn")}
          options={[{ value: "block", label: t`Block new bookings` }, { value: "warn", label: t`Only warn` }]} /> : null}
        {room ? <OutageImpact makerspaceId={makerspaceId} roomId={issue.subject_id} back={back} /> : null}
      </> : null}
      {counted ? <label className="eyebrow grid gap-1">{t`How many units`}<input className="desk-input" type="number" min="1" step="1"
        value={quantity} onChange={event => setQuantity(event.target.value)} /></label> : null}
      {change.error ? <p role="alert" className="text-sm text-danger">{change.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={change.isPending}>{change.isPending ? t`Saving…` : t`Save`}</button>
      </div>
    </form>}
  </Modal>;
}
