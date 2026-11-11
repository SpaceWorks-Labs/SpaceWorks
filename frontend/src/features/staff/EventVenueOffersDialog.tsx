import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Modal } from "../../components/ui";
import { StructuredApiError, staffRequest } from "../../lib/api";
import { formatLocale } from "../../lib/format";
import { venueKeys, type VenueOffer } from "./eventVenueApi";

function windowText(window: { starts_at: string; ends_at: string }) {
  const format = (value: string) => new Date(value).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
  return `${format(window.starts_at)} – ${format(window.ends_at)}`;
}

function offerText(offer: VenueOffer) {
  if (offer.action === "cancel_booking") return t`The room booking #${offer.booking_id ?? ""} still holds the room. Cancel it too? Its own cancellation and refund rules apply.`;
  if (offer.action === "move_booking") return offer.proposed_window
    ? t`The room booking #${offer.booking_id ?? ""} no longer covers the event. Move it to ${windowText(offer.proposed_window)}? Normal availability, pricing and approval apply.`
    : t`The room booking #${offer.booking_id ?? ""} no longer covers the event.`;
  return t`A venue fee is set for this event (${offer.fee_status ?? ""}). Review it in Tickets & invites.`;
}

function failure(error: unknown) {
  if (error instanceof StructuredApiError && error.status === 409) return t`The room booking changed or the room is taken. Check the venue panel.`;
  return error instanceof Error ? error.message : t`That did not work. Try again.`;
}

/**
 * Decision 223 (m): after an event is cancelled or moved the server OFFERS the next steps for
 * the linked room booking and venue fee. Each one runs only when staff press its button,
 * through the booking's own endpoint; offers this actor may not take say whom to ask.
 */
export function EventVenueOffersDialog({ makerspaceId, eventId, offers, onClose, onReviewFee }: {
  makerspaceId: number; eventId: number; offers: VenueOffer[]; onClose: () => void; onReviewFee?: () => void;
}) {
  const client = useQueryClient();
  const [done, setDone] = useState<string[]>([]);
  const run = useMutation({
    mutationFn: (offer: VenueOffer) => offer.action === "cancel_booking"
      ? staffRequest(`/admin/bookings/${offer.booking_id}/cancel/`, { method: "POST", body: JSON.stringify({ reason: t`The event was cancelled.` }) })
      : staffRequest(`/admin/bookings/${offer.booking_id}/time/`, { method: "POST", body: JSON.stringify(offer.proposed_window) }),
    onSuccess: async (_result, offer) => {
      setDone(rows => [...rows, offer.action]);
      await Promise.all([
        client.invalidateQueries({ queryKey: venueKeys.panel(makerspaceId, eventId) }),
        client.invalidateQueries({ queryKey: ["event-venue-booking"] }),
        client.invalidateQueries({ queryKey: ["booking-space"] }),
        client.invalidateQueries({ queryKey: ["booking-queue", makerspaceId] }),
        client.invalidateQueries({ queryKey: ["bookings", makerspaceId] }),
      ]);
    },
  });
  return <Modal open={offers.length > 0} onClose={onClose} title={t`What about the room?`} footer={
    <div className="desk-actions flex justify-end"><button type="button" className="desk-button w-full sm:w-auto" disabled={run.isPending} onClick={onClose}>{t`Done`}</button></div>}>
    <div className="grid gap-3 text-sm">
      <p>{t`Nothing was changed on the room booking or the venue fee. Choose what to do next.`}</p>
      <ul className="grid gap-3">
        {offers.map(offer => <li key={`${offer.action}:${offer.booking_id ?? ""}`} className="grid gap-2 rounded-md border border-line p-3">
          <p>{offerText(offer)}</p>
          {done.includes(offer.action) ? <p role="status" className="text-success-ink">{offer.action === "cancel_booking" ? t`Room booking cancelled.` : t`Room booking moved.`}</p>
            : offer.action === "change_venue_fee" ? (offer.allowed && onReviewFee ? <button type="button" className="desk-button w-fit" onClick={onReviewFee}>{t`Review venue fee`}</button> : null)
            : offer.allowed && offer.booking_id && (offer.action === "cancel_booking" || offer.proposed_window)
              ? <button type="button" className={offer.action === "cancel_booking" ? "desk-button-danger w-fit" : "desk-button w-fit"} disabled={run.isPending} onClick={() => run.mutate(offer)}>
                {offer.action === "cancel_booking" ? t`Cancel the room booking` : t`Move the room booking`}</button>
              : <p className="text-muted">{t`Ask a Booking Manager to change the room booking.`}</p>}
        </li>)}
      </ul>
      {run.error ? <p role="alert" className="text-danger">{failure(run.error)}</p> : null}
    </div>
  </Modal>;
}
