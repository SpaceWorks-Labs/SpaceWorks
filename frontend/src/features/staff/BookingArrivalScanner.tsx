import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookingPassPrint } from "./BookingPassPrint";
import QrScanner from "../../components/ui/QrScanner";
import { staffRequest } from "../../lib/api";
import type { BookingArrival } from "../../generated/api";

export function BookingArrivalScanner({ makerspaceId, spaceId }: { makerspaceId: number; spaceId: number }) {
  const [camera, setCamera] = useState(false);
  const [credential, setCredential] = useState("");
  const [result, setResult] = useState<BookingArrival | null>(null);
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
  // Credentials stay in the input's component state, never mutation variables/keys.
  const resolve = useMutation({ mutationFn: () => staffRequest<BookingArrival>(path + "resolve/", { method: "POST", body: JSON.stringify({ credential }) }),
    onSuccess: setResult });
  const confirm = useMutation({ mutationFn: () => staffRequest<BookingArrival>(path + "confirm/", { method: "POST", body: JSON.stringify({ credential }) }),
    onSuccess: async (value) => { setResult(value); setCredential(""); await invalidate(); }, onError: () => setResult(null) });
  const reverse = useMutation({ mutationFn: () => staffRequest<BookingArrival>(path + `${result!.booking_id}/reverse/`, { method: "POST", body: "{}" }),
    onSuccess: async (value) => { setResult(value); setCredential(""); await invalidate(); }, onError: () => setResult(null) });
  const busy = resolve.isPending || confirm.isPending || reverse.isPending;
  const error = resolve.error ?? confirm.error ?? reverse.error;
  function submit(event: FormEvent) { event.preventDefault(); setResult(null); confirm.reset(); reverse.reset(); resolve.mutate(); }
  return <section aria-label="Booking arrival scanner" className="grid gap-3 rounded-lg border border-line p-4">
    <h3 className="title-section">QR arrival</h3>
    <p className="text-sm text-muted">Scan or paste the private booking QR for this resource. Resolve checks details; confirm records arrival. Arrival does not complete a booking or authorize physical access.</p>
    <button className="desk-button-secondary w-fit" type="button" disabled={busy} onClick={() => setCamera(true)}>Scan with camera</button>
    {camera ? <QrScanner onClose={() => setCamera(false)} onScan={(value) => { setCredential(value); setResult(null); setCamera(false); resolve.reset(); confirm.reset(); reverse.reset(); }} /> : null}
    <form onSubmit={submit} className="grid gap-2">
      <label className="grid gap-1 text-sm">Booking QR<input className="desk-input" value={credential} autoComplete="off" spellCheck={false} maxLength={128} disabled={busy}
        onChange={(event) => { setCredential(event.target.value); setResult(null); resolve.reset(); confirm.reset(); reverse.reset(); }} /></label>
      <button className="desk-button-secondary w-fit" disabled={busy || !credential} type="submit">{resolve.isPending ? "Resolving..." : "Resolve QR"}</button>
    </form>
    {error ? <p role="alert" className="text-danger">{error.message}</p> : null}
    {result ? <div className="grid gap-2" aria-live="polite">
      <p className="font-semibold">{result.display_name} - {result.space_name}</p>
      <p>{new Date(result.starts_at).toLocaleString(undefined, { timeZone: result.timezone })} - {new Date(result.ends_at).toLocaleString(undefined, { timeZone: result.timezone })} ({result.timezone})</p>
      <p>{result.status.replace(/_/g, " ")} - {result.arrived_at ? "Arrival recorded" : "No active arrival"}</p>
      <p className="text-sm text-muted">Waiver: {result.waiver_state.replace(/_/g, " ")} (advisory)</p>
      {result.can_arrive && !result.arrived_at && credential ? <button type="button" className="desk-button-primary w-fit" disabled={busy} onClick={() => confirm.mutate()}>Confirm arrival</button> : null}
      {result.can_print_pass ? <BookingPassPrint key={result.booking_id} spaceId={spaceId} bookingId={result.booking_id} disabled={busy} /> : null}
      {result.can_reverse ? <button type="button" className="desk-button-danger w-fit" disabled={busy} onClick={() => reverse.mutate()}>Reverse recorded arrival</button> : null}
    </div> : null}
  </section>;
}
