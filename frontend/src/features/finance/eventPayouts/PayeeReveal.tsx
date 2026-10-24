import { useEffect, useState } from "react";
import { memberRequest, staffRequest } from "../../../lib/api";
import { memberPayoutPath, payoutPath } from "./api";
import { reasonIsValid, scopeIdentity } from "./format";
import { usePrivateRequest } from "./usePrivateRequest";
import type { FinanceScope } from "./types";

/** Both owner and finance inspect through the dedicated audited POST. */
type RevealProps = { obligationId: string; version: number; allowed?: boolean }
  & ({ scope: FinanceScope; actorId?: never } | { actorId: number; scope?: never });
export function PayeeReveal({ scope, actorId, obligationId, version, allowed = false }: RevealProps) {
  const identity = `${scopeIdentity(scope?.actorId ?? actorId ?? 0, scope?.makerspaceId)}:${obligationId}:${version}`;
  const request = usePrivateRequest<{ details: Record<string, string> }>(identity);
  const [reason, setReason] = useState("");
  const { clear } = request;
  useEffect(() => { if (!allowed) clear(); }, [allowed, clear]);
  useEffect(() => {
    if (!request.data) return;
    const timer = window.setTimeout(clear, 30_000);
    return () => window.clearTimeout(timer);
  }, [request.data, clear]);
  if (!allowed) return null;
  return <section aria-label="Private payee inspection" className="grid gap-3 rounded-2xl border border-line p-4">
    <h2 className="font-semibold">Inspect routing details</h2><p className="text-sm text-muted">This access is audited. Details hide after 30 seconds or when you leave this view.</p>
    <label className="grid gap-1 text-sm">Inspection reason code<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label>
    <button type="button" className="desk-button min-h-11" disabled={request.pending || !reasonIsValid(reason)} onClick={() => {
      const operation = crypto.randomUUID();
      void request.run(signal => {
        const options = { method: "POST", cache: "no-store" as const, signal, headers: { "Idempotency-Key": operation },
          body: JSON.stringify({ operation_id: operation, expected_version: version, purpose: "verify_routing", reason_code: reason }) };
        return scope ? staffRequest(`${payoutPath(scope)}/${encodeURIComponent(obligationId)}/payee/reveal/`, options)
          : memberRequest(`${memberPayoutPath(obligationId)}/payee/reveal/`, options);
      });
    }}>Reveal for inspection</button>
    {request.failed ? <p role="alert">Details could not be revealed. Reauthenticate or reload and try again.</p> : null}
    {request.data ? <><dl className="grid gap-2">{Object.entries(request.data.details).map(([key, value]) =>
      <div key={key}><dt className="text-sm text-muted">{key.replace(/_/g, " ")}</dt><dd className="break-all">{value}</dd></div>)}</dl>
      <button type="button" className="desk-button min-h-11" onClick={clear}>Hide details</button></> : null}
  </section>;
}
