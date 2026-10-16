import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ScanWorkbench } from "../../components/ui";
import { BookingPassPrint } from "./BookingPassPrint";
import { opsStatusLabel } from "./opsPresentation";
import { staffRequest } from "../../lib/api";
import type { BookingArrival } from "../../generated/api";

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
      setRecent((rows) => [{ key: `${value.booking_id}:${Date.now()}`, label: `${value.display_name} arrival reversed`, meta: value.space_name, tone: "warn" as const }, ...rows].slice(0, 5));
      await invalidate();
    }, onError: () => setResult(null) });
  const busy = resolve.isPending || confirm.isPending || reverse.isPending;
  const error = resolve.error ?? confirm.error ?? reverse.error;
  const clear = () => { setResult(null); forget(); resolve.reset(); confirm.reset(); reverse.reset(); };
  function find(value: string) {
    credentialRef.current = value; setCredential(value);
    setResult(null); confirm.reset(); reverse.reset(); resolve.mutate();
  }
  const canConfirm = Boolean(result?.can_arrive && !result.arrived_at && credential);
  const time = (iso: string, zone: string) => new Date(iso).toLocaleString(undefined, { timeZone: zone });
  return <section aria-labelledby="booking-arrival-title" className="grid gap-4">
    <div><h2 id="booking-arrival-title" className="title-panel">QR arrival</h2>
      <p className="mt-1 text-sm text-muted">Scan or paste the private booking QR for this resource. Resolve checks details; confirm records arrival. Arrival does not complete a booking or authorize physical access.</p></div>
    <ScanWorkbench onFind={find} searchLabel="Booking QR" helper="Paste the private booking QR. Check the details before confirming arrival."
      cameraLabel="Hold the booking QR inside the frame" findPending={busy} recent={recent} recentTitle="Recent arrivals"
      result={result ? { title: result.display_name, tone: result.arrived_at || result.can_arrive ? "success" : "warn",
        summary: <div className="grid gap-2">
          <p>{result.space_name}</p>
          <p>{time(result.starts_at, result.timezone)} – {time(result.ends_at, result.timezone)} ({result.timezone})</p>
          <p>{opsStatusLabel(result.status)} · {result.arrived_at ? "Arrival recorded" : "No active arrival"}</p>
          <p className="text-base">Waiver: {result.waiver_state.replace(/_/g, " ")} (advisory)</p>
        </div>,
        next: canConfirm ? { label: "Confirm arrival", onClick: () => confirm.mutate(), disabled: busy, disabledReason: busy ? "Wait for the current request to finish." : undefined }
          : { label: "Scan another", onClick: clear },
      } : error ? { title: "Couldn’t record arrival", tone: "danger", summary: error.message, next: { label: "Scan another", onClick: clear } } : undefined}
      controls={result && (result.can_print_pass || result.can_reverse || canConfirm) ? <div className="flex flex-wrap items-start gap-2">
        {canConfirm ? <button className="desk-button" type="button" disabled={busy} onClick={clear}>Scan another</button> : null}
        {result.can_print_pass ? <BookingPassPrint key={result.booking_id} spaceId={spaceId} bookingId={result.booking_id} disabled={busy} /> : null}
        {result.can_reverse ? <button type="button" className="desk-button-danger" disabled={busy} onClick={() => reverse.mutate()}>Reverse recorded arrival</button> : null}
      </div> : undefined} />
  </section>;
}
