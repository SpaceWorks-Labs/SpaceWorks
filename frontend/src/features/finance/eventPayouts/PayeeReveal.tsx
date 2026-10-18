import { useEffect, useRef, useState } from "react";
import { staffRequest } from "../../../lib/api";
import { payoutPath } from "./api";
import type { FinanceScope } from "./types";

/** Plaintext lives only in component memory, never a Query or mutation cache. */
export function PayeeReveal({ scope, obligationId, version }: { scope: FinanceScope; obligationId: string; version: number }) {
  const [details, setDetails] = useState<Record<string, string> | null>(null);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const inflight = useRef<AbortController | null>(null);
  useEffect(() => {
    const clear = () => { inflight.current?.abort(); setDetails(null); setPending(false); };
    const hidden = () => { if (document.visibilityState !== "visible") clear(); };
    const timer = window.setInterval(clear, 30_000);
    document.addEventListener("visibilitychange", hidden);
    window.addEventListener("blur", clear);
    return () => { clear(); window.clearInterval(timer); document.removeEventListener("visibilitychange", hidden); window.removeEventListener("blur", clear); };
  }, [obligationId, version]);
  const reveal = async () => {
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    const operation = crypto.randomUUID();
    setPending(true); setError(false); setDetails(null);
    try {
      const response = await staffRequest<{ details: Record<string, string> }>(`${payoutPath(scope)}/${obligationId}/payee/reveal/`, {
        method: "POST", cache: "no-store", signal: controller.signal, headers: { "Idempotency-Key": operation },
        body: JSON.stringify({ operation_id: operation, expected_version: version, purpose: "verify_routing", reason_code: reason }),
      });
      if (!controller.signal.aborted && document.visibilityState === "visible") setDetails(response.details);
    } catch { if (!controller.signal.aborted) setError(true); }
    finally { if (!controller.signal.aborted) setPending(false); }
  };
  return <section aria-label="Private payee inspection" className="grid gap-3 rounded-2xl border border-line p-4">
    <h2 className="font-semibold">Inspect routing details</h2><p className="text-sm text-muted">This access is audited. Details hide when you leave this view.</p>
    <label className="grid gap-1 text-sm">Reason code<input className="desk-input" pattern="[a-z][a-z0-9_]{0,63}" value={reason} onChange={event => setReason(event.target.value)} /></label>
    <button type="button" className="desk-button min-h-11" disabled={pending || !/^[a-z][a-z0-9_]{0,63}$/.test(reason)} onClick={() => { void reveal(); }}>Reveal for inspection</button>
    {error ? <p role="alert">Details could not be revealed. Reauthenticate or reload and try again.</p> : null}
    {details ? <><dl className="grid gap-2">{Object.entries(details).map(([key, value]) => <div key={key}><dt className="text-sm text-muted">{key.replace(/_/g, " ")}</dt><dd className="break-all">{value}</dd></div>)}</dl>
      <button type="button" className="desk-button min-h-11" onClick={() => setDetails(null)}>Hide details</button></> : null}
  </section>;
}
