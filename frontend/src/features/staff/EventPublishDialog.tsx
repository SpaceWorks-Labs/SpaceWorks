import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import { Modal } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { useEventVenue, venueStateText, venueWarningText, type VenuePanel } from "./eventVenueApi";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

/** Server refusals the publish dialog explains in place (the generic event error copy covers the rest). */
export function publishErrorText(error: unknown) {
  if (!(error instanceof StructuredApiError)) return "";
  if (error.code === "venue_booking_blocked") return t`The room booking is no longer usable. Replace the room, or tick “Publish without a room” to publish anyway.`;
  const body = error.body as { code?: string; registration_audience?: unknown } | undefined;
  if (error.code === "audience_requires_membership" || body?.code === "audience_requires_membership") {
    return t`Membership is off, so nobody can register for a members-only event. Turn on account registration for events or choose another audience.`;
  }
  return "";
}

/**
 * Decision 223 (g): the publish confirmation reads the venue first. A pending room warns; a
 * rejected, cancelled or missing room blocks unless the organizer explicitly publishes without
 * a room (the server audits that). A venue fee that will be charged is disclosed.
 */
export function EventPublishDialog({ open, makerspaceId, eventId, pending, error, onCancel, onPublish }: {
  open: boolean; makerspaceId: number; eventId: number; pending: boolean; error: unknown;
  onCancel: () => void; onPublish: (options: { publish_without_room?: boolean }) => void;
}) {
  const [withoutRoom, setWithoutRoom] = useState(false);
  const venue = useEventVenue(makerspaceId, eventId, open);
  // A 409 means the room changed after the dialog opened: reread it so the override is offered.
  const stale = error instanceof StructuredApiError && error.code === "venue_booking_blocked";
  useEffect(() => { if (stale) void venue.refetch(); }, [stale, error]); // eslint-disable-line react-hooks/exhaustive-deps -- refetch the venue only when the 409 appears or a new error arrives; `venue` is a new object each render
  // A venue panel that cannot be read (Bookings off, no access) never blocks publishing: the server re-checks.
  const panel: VenuePanel | undefined = venue.isError ? undefined : venue.data;
  const blocked = Boolean(panel?.requires_override) && !withoutRoom;
  const close = () => { setWithoutRoom(false); onCancel(); };
  const refusal = publishErrorText(error);
  return <Modal open={open} onClose={close} title={t`Publish event`} footer={
    <div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
      <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={close}>{t`Cancel`}</button>
      <button type="button" className="desk-button-primary w-full sm:w-auto" disabled={pending || venue.isPending || blocked}
        onClick={() => onPublish(panel?.requires_override && withoutRoom ? { publish_without_room: true } : {})}>
        {pending ? <><BoxArt size={16} mono />{t`Publishing…`}</> : t`Publish`}</button>
    </div>}>
    <div className="grid gap-3 text-sm">
      <p>{t`Publishing opens registration and shows the event wherever it is listed.`}</p>
      {venue.isPending ? <LogoLoader label={t`Checking the venue…`} size={48} className="min-h-16 py-3" /> : null}
      {panel ? <section aria-label={t`Venue check`} className="grid gap-2 rounded-md border border-line p-3">
        <h3 className="font-semibold text-ink">{t`Venue`}</h3>
        <p role={panel.venue.state === "blocked" ? "alert" : undefined}>{venueStateText(panel.venue)}</p>
        {panel.warnings.length ? <ul className="grid list-disc gap-1 pl-5" aria-label={t`Warnings`}>
          {panel.warnings.map(warning => <li key={warning.code}>{venueWarningText(warning)}</li>)}
        </ul> : null}
        {panel.venue_fee?.will_charge_on_publish ? <p role="status">{t`Publishing charges the configured venue fee to its payer.`}</p> : null}
        {panel.requires_override ? <label className="flex min-h-11 items-start gap-2">
          <input type="checkbox" className="mt-1 h-4 w-4" checked={withoutRoom} onChange={event => setWithoutRoom(event.target.checked)} />
          <span>{t`Publish without a room. Attendees see no confirmed venue and no venue fee is charged. This is recorded in the audit log.`}</span>
        </label> : null}
      </section> : null}
      {refusal ? <p role="alert" className="text-danger">{refusal}</p> : null}
    </div>
  </Modal>;
}
