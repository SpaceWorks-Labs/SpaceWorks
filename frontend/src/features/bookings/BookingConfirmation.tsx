import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { memberRequestBlob } from "../../lib/api";
import { confirmationPath, downloadBookingFile, useBookingConfirmation } from "./bookingConfirmationApi";

function ConfirmationQr({ slug, token, revision }: { slug: string; token: string; revision: string }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let imageUrl = "";
    memberRequestBlob(confirmationPath(slug, token) + "confirmation.png").then((blob) => {
      if (!active) return;
      imageUrl = URL.createObjectURL(blob);
      setUrl(imageUrl);
    }).catch(() => { if (active) setError("Unable to load QR. Refresh the confirmation to retry."); });
    return () => { active = false; if (imageUrl) URL.revokeObjectURL(imageUrl); };
  }, [slug, token, revision]);
  return error ? <p role="alert" className="text-danger">{error}</p> : url ? <img className="max-w-full" src={url} alt="Private booking QR for staff arrival scanning" referrerPolicy="no-referrer" /> : <p role="status">Loading private QR...</p>;
}

export function BookingConfirmation({ slug, token, onClose }: { slug: string; token: string; onClose?: () => void }) {
  const { detail, rotate } = useBookingConfirmation(slug, token);
  const [qrRefresh, setQrRefresh] = useState(0);
  const download = useMutation({ mutationFn: (kind: "png" | "ics") => downloadBookingFile(slug, token, kind) });
  const booking = detail.error ? undefined : detail.data;
  const error = detail.error ?? rotate.error ?? download.error;
  function refreshConfirmation() {
    // Remount the QR to retry its PNG with fresh loading/error state, even for the same credential.
    setQrRefresh((value) => value + 1);
    void detail.refetch();
  }
  return <section aria-label="Private booking confirmation" className="mt-3 grid gap-3 rounded-lg border border-line bg-panel p-4">
    <h3 className="title-section">Booking confirmation</h3>
    <p className="text-sm text-muted">Keep this QR private. Staff scan it to record arrival from 30 minutes before your booking until its end.</p>
    {detail.isPending ? <p role="status">Loading confirmation...</p> : null}
    {error ? <p role="alert" className="text-danger">{error.message}</p> : null}
    <button type="button" className="desk-button-secondary w-fit" onClick={refreshConfirmation} disabled={detail.isFetching}>Refresh confirmation</button>
    {booking ? <>
      <p>{booking.space_name} - {booking.status.replace(/_/g, " ")}</p>
      <p>{new Date(booking.starts_at).toLocaleString(undefined, { timeZone: booking.timezone })} - {new Date(booking.ends_at).toLocaleString(undefined, { timeZone: booking.timezone })} ({booking.timezone})</p>
      <p>{booking.location}</p><p className="whitespace-pre-wrap">{booking.description}</p>
      {booking.arrived_at ? <p role="status">Arrival recorded. Completion is recorded separately by staff.</p> : null}
      {booking.can_cancel ? <p className="text-sm">Cancel or reschedule in My bookings before {new Date(booking.cancellation_cutoff_at).toLocaleString(undefined, { timeZone: booking.timezone })}.</p> : null}
      {booking.qr_value ? <ConfirmationQr key={`${booking.qr_value}:${qrRefresh}`} slug={slug} token={token} revision={booking.qr_value} /> : null}
      <div className="flex flex-wrap gap-2">
        <a className="desk-button-secondary" href={booking.google_calendar_url} target="_blank" rel="noreferrer">Google Calendar</a>
        <button type="button" className="desk-button-secondary" disabled={download.isPending} onClick={() => download.mutate("ics")}>Download calendar</button>
        {booking.qr_value ? <><button type="button" className="desk-button-secondary" disabled={download.isPending} onClick={() => download.mutate("png")}>Download QR PNG</button>
          <button type="button" className="desk-button-secondary" disabled={rotate.isPending} onClick={() => rotate.mutate()}>Replace private QR</button></> : null}
      </div>
    </> : null}
    {onClose ? <button className="desk-button-ghost w-fit" type="button" onClick={onClose}>Close confirmation</button> : null}
  </section>;
}
