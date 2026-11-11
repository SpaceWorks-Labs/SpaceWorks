import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, ErrorText, Skeleton, TicketCard } from "../../components/ui";
import { memberRequestBlob } from "../../lib/api";
import { bookingStatusLabel } from "./bookingStatusLabel";
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
    }).catch(() => { if (active) setError(t`Unable to load QR. Refresh the confirmation to retry.`); });
    return () => { active = false; if (imageUrl) URL.revokeObjectURL(imageUrl); };
  }, [slug, token, revision]);
  return error ? <p role="alert" className="grid h-full place-items-center text-center text-sm text-danger">{error}</p>
    : url ? <img className="max-w-full" src={url} alt={t`Private booking QR for staff arrival scanning`} referrerPolicy="no-referrer" />
    : <div role="status" aria-label={t`Loading private QR...`} className="h-full"><Skeleton className="h-full w-full" /></div>;
}

const statusWords = bookingStatusLabel;

export function BookingConfirmation({ slug, token, onClose }: { slug: string; token: string; onClose?: () => void }) {
  const { detail, rotate } = useBookingConfirmation(slug, token);
  const [qrRefresh, setQrRefresh] = useState(0);
  const download = useMutation({ mutationFn: (kind: "png" | "ics" | "pdf") => downloadBookingFile(slug, token, kind) });
  const booking = detail.error ? undefined : detail.data;
  const error = detail.error ?? rotate.error ?? download.error;
  function refreshConfirmation() {
    // Remount the QR to retry its PNG with fresh loading/error state, even for the same credential.
    setQrRefresh((value) => value + 1);
    void detail.refetch();
  }
  const when = booking ? `${new Date(booking.starts_at).toLocaleString(formatLocale(), { timeZone: booking.timezone })} – ${new Date(booking.ends_at).toLocaleString(formatLocale(), { timeZone: booking.timezone })} (${booking.timezone})` : "";
  const fields = booking ? [{ label: t`Status`, value: statusWords(booking.status) }, { label: t`When`, value: when },
    ...(booking.location ? [{ label: t`Location`, value: booking.location }] : [])] : [];
  const caption = "Keep this QR private. Staff scan it to record arrival from 30 minutes before your booking until its end.";
  return <section aria-label={t`Private booking confirmation`} className="mt-3 grid min-w-0 gap-4">
    {detail.isPending ? <p role="status" className="text-sm text-muted">{t`Loading confirmation...`}</p> : null}
    {error ? <ErrorText message={error.message} /> : null}
    {booking ? <>
      {booking.qr_value ? <TicketCard organisation="Booking confirmation" title={booking.space_name} fields={fields} caption={caption}
        qr={<ConfirmationQr key={`${booking.qr_value}:${qrRefresh}`} slug={slug} token={token} revision={booking.qr_value} />} />
        : <Card className="grid gap-4"><div><p className="text-sm text-muted">{t`Booking confirmation`}</p><h2 className="title-panel mt-1">{booking.space_name}</h2></div>
          <dl className="grid grid-cols-2 gap-4">{fields.map((field) => <div key={field.label} className="min-w-0"><dt className="eyebrow">{field.label}</dt>
            <dd className="mt-1 break-words text-sm font-semibold text-ink">{field.value}</dd></div>)}</dl>
          <p className="text-sm text-muted">{caption}</p></Card>}
      {booking.description ? <p className="whitespace-pre-wrap text-sm">{booking.description}</p> : null}
      {booking.arrived_at ? <p role="status" className="text-sm text-success-ink">{t`Arrival recorded. Completion is recorded separately by staff.`}</p> : null}
      {booking.can_cancel ? <p className="text-sm text-muted">{t`Cancel or reschedule in My bookings before ${new Date(booking.cancellation_cutoff_at).toLocaleString(formatLocale(), { timeZone: booking.timezone })}.`}</p> : null}
      <div className="flex flex-wrap gap-2">
        <a className="desk-button" href={booking.google_calendar_url} target="_blank" rel="noreferrer">{t`Google Calendar`}</a>
        <button type="button" className="desk-button" disabled={download.isPending} onClick={() => download.mutate("ics")}>{t`Download calendar`}</button>
        {booking.pass_available ? <button type="button" className="desk-button" disabled={download.isPending} onClick={() => download.mutate("pdf")}>{t`Download printable pass`}</button> : null}
        {booking.qr_value ? <><button type="button" className="desk-button" disabled={download.isPending} onClick={() => download.mutate("png")}>{t`Download QR PNG`}</button>
          <button type="button" className="desk-button" disabled={rotate.isPending} onClick={() => rotate.mutate()}>{t`Replace private QR`}</button></> : null}
      </div>
    </> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-ghost" onClick={refreshConfirmation} disabled={detail.isFetching}>{t`Refresh confirmation`}</button>
      {onClose ? <button className="desk-button-ghost" type="button" onClick={onClose}>{t`Close confirmation`}</button> : null}
    </div>
  </section>;
}
