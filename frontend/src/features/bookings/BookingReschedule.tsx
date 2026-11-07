import { t } from "@lingui/core/macro";
import { Modal } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import type { MemberBooking } from "./MyBookings";

export function BookingReschedule({ booking, slug, onClose }: { booking: MemberBooking; slug: string; onClose: () => void }) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const client = useQueryClient();
  const save = useMutation({ mutationFn: () => memberRequest<MemberBooking>(`/public/${encodeURIComponent(slug)}/my-bookings/${booking.public_token}/reschedule/`, {
    method: "POST", body: JSON.stringify({ starts_at: new Date(start).toISOString(), ends_at: new Date(end).toISOString() }),
  }), onSuccess: async () => {
    await Promise.all([client.invalidateQueries({ queryKey: ["member", slug] }), client.invalidateQueries({ queryKey: ["public-space-availability"] })]);
    onClose();
  } });
  return <Modal open title={t`Reschedule booking`} onClose={onClose}><form className="mt-3 grid gap-2 rounded-lg border border-line p-3" aria-label={t`Reschedule booking`} onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
    <p className="text-sm">{t`Move ${booking.space_name}. The charge and approval status stay the same.`}</p>
    <label className="grid gap-1 text-sm">{t`New start (your local time)`}<input className="desk-input w-full min-w-0" type="datetime-local" required value={start} onChange={(event) => setStart(event.target.value)} /></label>
    <label className="grid gap-1 text-sm">{t`New end (your local time)`}<input className="desk-input w-full min-w-0" type="datetime-local" required min={start} value={end} onChange={(event) => setEnd(event.target.value)} /></label>
    {save.error ? <p role="alert" className="text-danger">{save.error.message}</p> : null}
    <div className="flex flex-wrap gap-2 [&>button]:flex-1 sm:[&>button]:flex-none"><button className="desk-button-primary" disabled={save.isPending}>{t`Save new time`}</button><button className="desk-button-ghost" type="button" disabled={save.isPending} onClick={onClose}>{t`Keep current time`}</button></div>
  </form></Modal>;
}
