import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ScanWorkbench } from "../../components/ui";
import { BookingPassPrint } from "./BookingPassPrint";
import { opsStatusLabel } from "./opsPresentation";
import { staffRequest } from "../../lib/api";
import type { BookingArrival as GeneratedArrival } from "../../generated/api";
import { DepartureForm, type DepartureInput } from "../bookings/DepartureForm";

/** Phase 2 adds the check-out projection; hand-typed until the client is regenerated. */
type BookingArrival = GeneratedArrival & { departed_at?: string | null; can_depart?: boolean };

/** Staff-side booking arrival: scan or paste, check the details, then confirm.
 *
 * Resolving is read-only; confirming records arrival. Arrival never completes a booking or authorizes
 * physical access, so the two steps stay separate exactly as in event check-in.
 */
export function BookingArrivalScanner({ makerspaceId, spaceId }: { makerspaceId: number; spaceId: number }) {
  // Credentials stay in this component (a ref for the request body, state for rendering), never in
  // mutation variables or query keys.
  const credentialRef = useRef("");
  const [credential, setCredential] = useState("");
  const [result, setResult] = useState<BookingArrival | null>(null);
  const [recent, setRecent] = useState<{ key: string; label: string; meta?: string; tone?: "success" | "warn" }[]>([]);
  const client = useQueryClient();
  const path = `/admin/spaces/${spaceId}/arrival/`;
  const invalidate = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["bookings", makerspaceId] }),
      client.invalidateQueries({ queryKey: ["booking-space", spaceId] }),
      client.invalidateQueries({ queryKey: ["member"] }),
      client.invalidateQueries({ queryKey: ["operations-report"] }),
    ]);
  };
  const forget = () => { credentialRef.current = ""; setCredential(""); };
  const resolve = useMutation({ mutationFn: () => staffRequest<BookingArrival>(path + "resolve/", { method: "POST", body: JSON.stringify({ credential: credentialRef.current }) }),
    onSuccess: setResult });
  const confirm = useMutation({ mutationFn: () => staffRequest<BookingArrival>(path + "confirm/", { method: "POST", body: JSON.stringify({ credential: credentialRef.current }) }),
    onSuccess: async (value) => {
      setResult(value); forget();
      setRecent((rows) => [{ key: `${value.booking_id}:${Date.now()}`, label: `${value.display_name} arrived`, meta: value.space_name, tone: "success" as const }, ...rows].slice(0, 5));
      await invalidate();
    }, onError: () => setResult(null) });
  const reverse = useMutation({ mutationFn: () => staffRequest<BookingArrival>(path + `${result!.booking_id}/reverse/`, { method: "POST", body: "{}" }),
    onSuccess: async (value) => {
      setResult(value); forget();
      setRecent((rows) => [{ key: `${value.booking_id}:${Date.now()}`, label: t`${value.display_name} arrival reversed`, meta: value.space_name, tone: "warn" as const }, ...rows].slice(0, 5));
      await invalidate();
    }, onError: () => setResult(null) });
  const depart = useMutation({ mutationFn: (input: DepartureInput) => staffRequest<BookingArrival>(path + `${result!.booking_id}/depart/`, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: async (value) => {
      setResult(value); forget();
      setRecent((rows) => [{ key: `${value.booking_id}:${Date.now()}`, label: t`${value.display_name} checked out`, meta: value.space_name, tone: "success" as const }, ...rows].slice(0, 5));
      await Promise.all([invalidate(), client.invalidateQueries({ queryKey: ["booking-issues", makerspaceId] })]);
    } });
  const busy = resolve.isPending || confirm.isPending || reverse.isPending || depart.isPending;
  const error = resolve.error ?? confirm.error ?? reverse.error;
  const clear = () => { setResult(null); forget(); resolve.reset(); confirm.reset(); reverse.reset(); depart.reset(); };
  function find(value: string) {
    credentialRef.current = value; setCredential(value);
    setResult(null); confirm.reset(); reverse.reset(); resolve.mutate();
  }
  const canConfirm = Boolean(result?.can_arrive && !result.arrived_at && credential);
  const time = (iso: string, zone: string) => new Date(iso).toLocaleString(formatLocale(), { timeZone: zone });
  return <section aria-labelledby="booking-arrival-title" className="grid gap-4">
    <div><h2 id="booking-arrival-title" className="title-panel">{t`QR arrival`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Scan or paste the private booking QR for this resource. Resolve checks details; confirm records arrival. Arrival does not complete a booking or authorize physical access.`}</p></div>
    <ScanWorkbench onFind={find} searchLabel="Booking QR" helper="Paste the private booking QR. Check the details before confirming arrival."
      cameraLabel="Hold the booking QR inside the frame" findPending={busy} recent={recent} recentTitle="Recent arrivals"
      result={result ? { title: result.display_name, tone: result.arrived_at || result.can_arrive ? "success" : "warn",
        summary: <div className="grid gap-2">
          <p>{result.space_name}</p>
          <p>{time(result.starts_at, result.timezone)} – {time(result.ends_at, result.timezone)} ({result.timezone})</p>
          <p>{opsStatusLabel(result.status)} · {result.arrived_at ? t`Arrival recorded` : t`No active arrival`}{result.departed_at ? t` · Checked out` : ""}</p>
          <p className="text-base">{t`Waiver: ${result.waiver_state.replace(/_/g, " ")} (advisory)`}</p>
        </div>,
        next: canConfirm ? { label: t`Confirm arrival`, onClick: () => confirm.mutate(), disabled: busy, disabledReason: busy ? "Wait for the current request to finish." : undefined }
          : { label: t`Scan another`, onClick: clear },
      } : error ? { title: t`Couldn’t record arrival`, tone: "danger", summary: error.message, next: { label: t`Scan another`, onClick: clear } } : undefined}
      controls={result && (result.can_print_pass || result.can_reverse || canConfirm || result.can_depart) ? <div className="flex flex-wrap items-start gap-2">
        {canConfirm ? <button className="desk-button" type="button" disabled={busy} onClick={clear}>{t`Scan another`}</button> : null}
        {result.can_print_pass ? <BookingPassPrint key={result.booking_id} spaceId={spaceId} bookingId={result.booking_id} disabled={busy} /> : null}
        {result.can_reverse ? <button type="button" className="desk-button-danger" disabled={busy} onClick={() => reverse.mutate()}>{t`Reverse recorded arrival`}</button> : null}
        {result.can_depart ? <div className="w-full rounded-lg border border-line p-3">
          <DepartureForm audience="staff" pending={depart.isPending} error={depart.error?.message} onSubmit={input => depart.mutate(input)} />
        </div> : null}
      </div> : undefined} />
  </section>;
}
