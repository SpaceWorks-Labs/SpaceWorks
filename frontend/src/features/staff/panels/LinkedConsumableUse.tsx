import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { PendingIntake } from "../../inventory/contextualIntake";
import { consumableKeys } from "./consumablesApi";
import { submitLinkedUse, fetchLinkedUseSources, type LinkedUseBody, type UseSource } from "./linkedConsumableApi";
import { PagePager } from "../../../components/ui";
import { LogoLoader } from "../../../components/LogoLoader";

function sourceLabel(source: UseSource, position: number) {
  const planned = source.planned_quantity; const used = source.used_quantity;
  return source.kind === "plan" ? t`Consumable plan ${position} · ${planned} planned · ${used} used`
    : t`Equipment request ${position} · ${planned} planned · ${used} used`;
}

export function LinkedConsumableUse({ tenant, product, scope, owner, admitted, acquire, onLockChange }: { tenant: number; product: number; scope: string; owner: PendingIntake<LinkedUseBody>; admitted: () => boolean; acquire: () => (() => void) | undefined; onLockChange: (locked: boolean) => void }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1); const [selection, setSelection] = useState<UseSource | null>(null);
  const [quantity, setQuantity] = useState("1"); const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false); const [denied, setDenied] = useState(false); const [message, setMessage] = useState("");
  const [uncertain, setUncertain] = useState(() => Boolean(owner.current(scope)));
  const wasUncertain = useRef(uncertain);
  useEffect(() => {
    const sync = () => { const exists = Boolean(owner.current(scope)); setUncertain(exists); onLockChange(exists); if (!exists) wasUncertain.current = false; };
    const unsubscribe = owner.subscribe(sync); sync(); return unsubscribe;
  }, [owner, scope, onLockChange]);
  const sources = useQuery({ queryKey: ["linked-consumable-sources", scope, product, page], enabled: !denied, retry: false, queryFn: () => { if (!admitted()) throw new Error(t`Session changed.`); return fetchLinkedUseSources(tenant, product, page); } });
  async function send(body: Readonly<LinkedUseBody>) {
    if (!admitted()) { setDenied(true); return; }
    const release = acquire(); if (!release) return;
    setBusy(true); setMessage("");
    try {
      await submitLinkedUse(tenant, product, body);
      if (owner.complete(scope, body)) { onLockChange(false); wasUncertain.current = false; setUncertain(false); setSelection(null); setNote(""); setMessage(t`Use recorded.`); }
      void client.invalidateQueries({ queryKey: consumableKeys.all(tenant) });
      void client.invalidateQueries({ queryKey: ["inventory", tenant] });
      void client.invalidateQueries({ queryKey: ["linked-consumable-sources", scope, product] });
    } catch (error) {
      const status = (error as { status?: number })?.status;
      if (status === 400 && !wasUncertain.current) { if (owner.complete(scope, body)) { onLockChange(false); setMessage(t`Check the amount and try again.`); } }
      else { wasUncertain.current = true; setUncertain(true); setMessage(t`The result may be unknown. Retry the same use.`);
        if ([401, 403, 404].includes(status ?? 0)) { setDenied(true); setSelection(null); setNote(""); client.removeQueries({ queryKey: ["linked-consumable-sources", scope, product] }); } }
    } finally { release(); setBusy(false); }
  }
  function begin() {
    const amount = Number(quantity);
    if (!admitted()) { setDenied(true); return; }
    if (!selection || !Number.isInteger(amount) || amount < 1 || amount > 100000) return;
    const release = acquire(); if (!release) return;
    const body = owner.begin(scope, { operation_id: crypto.randomUUID(), quantity: amount, note: note.trim(), allocation_id: selection.kind === "allocation" ? selection.id : null, plan_id: selection.kind === "plan" ? selection.id : null });
    onLockChange(true);
    release();
    void send(body);
  }
  if (denied) return <p role="status">{t`Linked use is unavailable for your access.`}</p>;
  return <section className="grid gap-2 border-t border-line pt-4" data-replay-block><h3 className="text-sm font-semibold text-ink">{t`Record use against a plan`}</h3>
    {sources.isPending ? <LogoLoader label={t`Loading plans…`} size={48} className="min-h-16 py-3" /> : sources.isError ? <p className="text-sm text-danger" role="alert">{t`Plans are unavailable.`}</p> : <>
      {!sources.data.results.length ? <p className="text-sm text-muted">{t`No open plans or requests use this item.`}</p> : null}
      {sources.data.results.map((source, index) => <button key={`${source.kind}:${source.id}`} type="button" className="desk-button justify-start text-left" disabled={busy || uncertain} aria-pressed={selection?.kind === source.kind && selection.id === source.id} onClick={() => setSelection(source)}>{sourceLabel(source, index + 1)}</button>)}
      <PagePager page={page} setPage={setPage} next={sources.data.next} disabled={busy || uncertain} />
    </>}
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`How many were used`}<input className="desk-input font-normal" type="number" min="1" max="100000" value={quantity} disabled={busy || uncertain} onChange={event => setQuantity(event.target.value)} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Note (optional)`}<input className="desk-input font-normal" maxLength={200} value={note} disabled={busy || uncertain} onChange={event => setNote(event.target.value)} /></label>
    {uncertain ? <button type="button" className="desk-button w-fit" disabled={busy} onClick={() => { const body = owner.current(scope); if (body) void send(body); }}>{t`Retry the same use`}</button> : <button type="button" className="desk-button-primary w-fit" disabled={busy || !selection || !Number.isInteger(Number(quantity)) || Number(quantity) < 1 || Number(quantity) > 100000} onClick={begin}>{t`Record linked use`}</button>}
    {message ? <p role="status">{message}</p> : null}
  </section>;
}
