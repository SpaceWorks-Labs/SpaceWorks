import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import { memberPayoutKey, memberPayoutPath, useCommandIdentity, usePayeeContext } from "./api";
import { scopeIdentity } from "./format";
import { fieldLabel, templateFields } from "./payeeTemplates";
import { usePrivateRequest } from "./usePrivateRequest";
import { collectedPayee, permits } from "./types";
import type { CommandResult, PayeeContext, PayoutDetail } from "./types";

export function PayeeCollection({ actorId, payout }: { actorId: number; payout: PayoutDetail }) {
  const query = usePayeeContext(actorId, payout.id);
  if (query.isPending) return <p role="status">{t`Loading enabled payment methods…`}</p>;
  if (query.error) return <div role="alert">{t`Payment methods could not be loaded. `}<button className="desk-button min-h-11" onClick={() => { void query.refetch(); }}>{t`Retry payment methods`}</button></div>;
  if (!query.data) return null;
  return <CollectionForm key={`${scopeIdentity(actorId)}:${payout.id}:${payout.version}:${JSON.stringify(query.data.templates)}:${query.data.allowed_actions?.join()}`}
    actorId={actorId} payout={payout} context={query.data} />;
}

function CollectionForm({ actorId, payout, context }: { actorId: number; payout: PayoutDetail; context: PayeeContext }) {
  const client = useQueryClient();
  const identity = useCommandIdentity();
  const request = usePrivateRequest<CommandResult>(`${scopeIdentity(actorId)}:${payout.id}:${payout.version}`);
  const [selection, setSelection] = useState("");
  const [details, setDetails] = useState<Record<string, string>>({});
  const [consent, setConsent] = useState(false);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const submitLock = useRef(false);
  const templates = context.templates.filter(choice => templateFields(choice) !== null);
  const chosen = templates.find(choice => choice.join(":") === selection);
  const fields = chosen ? templateFields(chosen) ?? [] : [];
  const payee = collectedPayee(context.payee);
  const editable = permits(payout, "submit_payee") && permits(context, "submit_payee") && payout.approved_minor > 0;
  const dirty = Object.values(details).some(Boolean);
  useEffect(() => {
    const clear = () => { setDetails({}); setConsent(false); };
    const hidden = () => { if (document.visibilityState !== "visible") clear(); };
    window.addEventListener("blur", clear); document.addEventListener("visibilitychange", hidden);
    return () => { window.removeEventListener("blur", clear); document.removeEventListener("visibilitychange", hidden); };
  }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const valid = editable && chosen && consent && fields.every(field => details[field]?.trim());
  const save = async () => {
    if (!valid || !chosen || submitLock.current) return;
    submitLock.current = true;
    try {
      const payload = { expected_version: payout.version, expected_payee_version: payee?.version ?? null,
        country: chosen[0], method: chosen[1], template_key: chosen[2], template_version: chosen[3],
        details: Object.fromEntries(fields.map(field => [field, details[field]])), disclosure_version: context.disclosure_version };
      // Retry identity retains only a digest, never raw routing values in a long-lived ref/cache.
      await request.run(async signal => {
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(payload)))))
          .map(byte => byte.toString(16).padStart(2, "0")).join("");
        if (signal.aborted) throw new Error("dismissed");
        const operation = identity.forPayload({ id: payout.id, digest });
        const result = await memberRequest<CommandResult>(`${memberPayoutPath(payout.id)}/payee/`, {
          method: "PUT", cache: "no-store", signal, headers: { "Idempotency-Key": operation },
          body: JSON.stringify({ ...payload, operation_id: operation }) });
        if (!signal.aborted) {
          setDetails({}); setConsent(false); identity.clear();
          await client.invalidateQueries({ queryKey: memberPayoutKey(actorId) });
        }
        return result;
      });
    } finally { submitLock.current = false; }
  };
  return <section className="grid gap-4 rounded-2xl border border-line bg-panel p-5" aria-label={t`Your payment routing`}>
    <h2 className="font-semibold">{t`Your payment routing`}</h2><p>{context.disclosure}</p>
    <p className="text-sm text-muted">{t`Routing values are visible only to you and authorized finance staff. Each edit creates a new revision for this reimbursement. Details clear when you leave this window.`}</p>
    {payee ? <><p>{payee.masked_details} · {payee.method.replace(/_/g, " ")} · {payee.verified ? t`Verified` : t`Awaiting finance review`}</p>
      {payee.correction ? <p role="status">{t`Finance requested a correction: ${payee.correction.reason_code.replace(/_/g, " ")} · ${payee.correction.note}`}</p> : null}</> : null}
    {editable ? templates.length ? <form className="grid gap-3" autoComplete="off" onSubmit={event => { event.preventDefault(); void save(); }}>
      <label className="grid gap-1">{t`Country and payment method`}<select className="desk-input" value={selection} disabled={request.pending} onChange={event => {
        setSelection(event.target.value); setDetails({}); setConsent(false);
      }}><option value="">{t`Choose an enabled method`}</option>{templates.map(choice => <option key={choice.join(":")} value={choice.join(":")}>{choice[0]} · {choice[1].replace(/_/g, " ")}</option>)}</select></label>
      {fields.map(field => <label key={field} className="grid gap-1">{fieldLabel(field)}{field === "account_type"
        ? <select className="desk-input" required value={details[field] ?? ""} disabled={request.pending} onChange={event => { setDetails({ ...details, [field]: event.target.value }); setConsent(false); }}>
          <option value="">{t`Choose account type`}</option><option value="checking">{t`Checking`}</option><option value="savings">{t`Savings`}</option></select>
        : <input className="desk-input" required type={field === "payout_email" ? "email" : "text"} autoComplete="off" spellCheck={false}
          maxLength={field === "delivery_instructions" ? 1000 : 200} disabled={request.pending} value={details[field] ?? ""}
          onChange={event => { setDetails({ ...details, [field]: event.target.value }); setConsent(false); }} />}</label>)}
      {chosen?.[1] === "paypal" || chosen?.[1] === "wise" ? <p className="text-sm text-muted">{t`Provide only your receiving email. Never provide a password, API key or login code.`}</p> : null}
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />{t`I checked these details and agree to their use for this reimbursement.`}</label>
      <button className="desk-button min-h-11" type="submit" disabled={!valid || request.pending}>{request.pending ? t`Saving routing…` : payee ? t`Submit corrected routing` : t`Submit payment routing`}</button>
      {dirty ? <button type="button" className="desk-button min-h-11" onClick={() => { setDetails({}); setConsent(false); }}>{t`Discard entered details`}</button> : null}
    </form> : <p>{t`No supported payment method is enabled. Contact finance to enable a country template before entering details.`}</p> : <p>{t`Payment routing is not currently requested.`}</p>}
    {permits(payout, "delete_payee") && permits(context, "delete_payee") ? <>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={deleteConfirmed} onChange={event => setDeleteConfirmed(event.target.checked)} />{t`Delete routing details when the retention policy permits.`}</label>
      <button type="button" className="desk-button-danger-outline min-h-11" disabled={!deleteConfirmed || request.pending} onClick={() => {
        const data = { expected_version: payout.version }; const operation = identity.forPayload({ action: "delete", id: payout.id, data });
        void request.run(async signal => {
          const result = await memberRequest<CommandResult>(`${memberPayoutPath(payout.id)}/payee/`, { method: "DELETE", cache: "no-store", signal,
            headers: { "Idempotency-Key": operation }, body: JSON.stringify({ ...data, operation_id: operation }) });
          if (!signal.aborted) await client.invalidateQueries({ queryKey: memberPayoutKey(actorId) }); return result;
        });
      }}>{t`Delete retained routing details`}</button></> : null}
    {request.failed ? <p role="alert">{t`Routing was not changed. Check the template, reload current versions and try again. Unpaid obligations and active retention holds prevent deletion.`}</p> : null}
    {request.data ? <p role="status">{t`Routing change recorded. The updated view shows only masked values.`}</p> : null}
  </section>;
}
