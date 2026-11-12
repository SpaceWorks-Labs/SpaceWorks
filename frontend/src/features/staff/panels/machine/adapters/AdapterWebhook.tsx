import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Callout, Field, RelativeTime, StatusPill } from "../../../../../components/ui";
import { StructuredApiError } from "../../../../../lib/api/errors";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Webhook } from "./adaptersApi";
import { BoxArt } from "../../../../../components/BoxSpinner";

/** The `whsec_` secret, shown exactly once after a save that created it or a rotation. */
function SecretReveal({ secret, onDone }: { secret: string; onDone: () => void }) {
  const [state, setState] = useState("");
  return <div className="grid gap-3 rounded-2xl border border-danger-line bg-panel p-4" role="group" aria-label={t`Webhook secret`}>
    <Callout size="inline" tone="warn" lead={t`Copy this secret now.`} body={t`It is shown once and cannot be read again. If you lose it, rotate it.`} />
    <label className="grid gap-1 text-sm font-semibold">{t`Signing secret`}<textarea className="desk-input min-h-16 w-full font-mono" readOnly value={secret} /></label>
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button" onClick={async () => {
        try { await navigator.clipboard.writeText(secret); setState(t`Copied. Clear your clipboard after use.`); } catch { setState(t`Copy unavailable. Select the secret and copy it by hand.`); }
      }}>{t`Copy secret`}</button>
      <button type="button" className="desk-button-primary" onClick={onDone}>{t`I've copied it`}</button></div>
    <p role="status" className="text-sm text-muted">{state}</p>
  </div>;
}

/** Optional push endpoint of an adapter: a content-free wake-up so the bridge need not poll. The work is still leased over the signed API. */
export function AdapterWebhook({ makerspaceId, adapterId }: { makerspaceId: number; adapterId: string }) {
  const client = useQueryClient();
  const hook = useQuery({ queryKey: adapterKeys.webhook(makerspaceId, adapterId), queryFn: () => adaptersApi.webhook(adapterId), retry: false });
  const deliveries = useQuery({ queryKey: adapterKeys.deliveries(makerspaceId, adapterId), queryFn: () => adaptersApi.deliveries(adapterId), refetchInterval: 30_000, enabled: hook.isSuccess });
  const [url, setUrl] = useState<string | null>(null);
  const [names, setNames] = useState<boolean | null>(null);
  const [secret, setSecret] = useState("");
  const [confirmRotate, setConfirmRotate] = useState(false);
  const current: Webhook | undefined = hook.data;
  const absent = hook.error instanceof StructuredApiError && hook.error.status === 404;
  const refresh = () => { void client.invalidateQueries({ queryKey: adapterKeys.webhook(makerspaceId, adapterId) }); void client.invalidateQueries({ queryKey: adapterKeys.deliveries(makerspaceId, adapterId) }); };
  const save = useMutation({ mutationFn: (body: { url: string; include_data: boolean }) => adaptersApi.setWebhook(adapterId, body),
    onSuccess: row => { setUrl(null); setNames(null); if (row.secret) setSecret(row.secret); refresh(); } });
  const rotate = useMutation({ mutationFn: () => adaptersApi.rotateWebhook(adapterId), onSuccess: row => { setConfirmRotate(false); if (row.secret) setSecret(row.secret); refresh(); } });
  const remove = useMutation({ mutationFn: () => adaptersApi.removeWebhook(adapterId), onSuccess: refresh });
  const shownUrl = url ?? current?.url ?? "";
  const shownNames = names ?? current?.include_data ?? false;
  const disabled = Boolean(current && !current.enabled);
  const error = save.error ?? rotate.error ?? remove.error;
  return <div className="grid gap-5">
    <p className="text-sm text-muted">{t`A webhook only wakes the bridge up when work is waiting. It carries no member or job details, and the work is still fetched over the bridge's signed connection.`}</p>
    {secret ? <SecretReveal secret={secret} onDone={() => setSecret("")} /> : null}
    {disabled ? <Callout size="inline" tone="danger" lead={t`This webhook switched itself off.`} body={current?.disabled_reason || t`It failed ten times in a row.`}
      action={{ label: t`Re-enable`, onClick: () => current && save.mutate({ url: current.url, include_data: current.include_data }) }} /> : null}
    <form className="grid gap-3 rounded-2xl border border-line bg-panel p-4" aria-label={t`Webhook settings`}
      onSubmit={event => { event.preventDefault(); save.mutate({ url: shownUrl.trim(), include_data: shownNames }); }}>
      <div className="flex flex-wrap items-center gap-2"><h3 className="title-section flex-1">{t`Webhook`}</h3>
        {current ? <StatusPill label={disabled ? t`Switched off` : t`On`} tone={disabled ? "danger" : "success"} /> : null}</div>
      <Field label={t`Endpoint URL`} hint={t`Must be a public https address. Private and local addresses are refused.`}>
        <input className="desk-input" type="url" inputMode="url" required maxLength={500} placeholder="https://" value={shownUrl} onChange={event => setUrl(event.target.value)} /></Field>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={shownNames} onChange={event => setNames(event.target.checked)} />
        <span><strong>{t`Include capability and command names`}</strong><span className="block text-muted">{t`Names only, never parameters, members or files. Off by default.`}</span></span></label>
      {error ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(error)}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="desk-button-primary" disabled={!shownUrl.trim() || save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : current ? t`Save webhook` : t`Create webhook`}</button>
        {current ? confirmRotate ? <span className="flex flex-wrap items-center gap-2"><span className="text-sm text-danger">{t`The old secret stops working at once.`}</span>
          <button type="button" className="desk-button" onClick={() => setConfirmRotate(false)}>{t`Keep it`}</button>
          <button type="button" className="desk-button-danger" disabled={rotate.isPending} onClick={() => rotate.mutate()}>{t`Rotate secret`}</button></span>
          : <button type="button" className="desk-button" onClick={() => setConfirmRotate(true)}>{t`Rotate secret`}</button> : null}
        {current && !disabled ? <button type="button" className="desk-button" disabled={remove.isPending} onClick={() => remove.mutate()}>{t`Turn off`}</button> : null}
      </div>
      {absent ? <p className="text-sm text-muted">{t`No webhook yet. The bridge polls instead.`}</p> : null}
    </form>
    {current ? <section className="grid gap-2" aria-label={t`Deliveries`}><h3 className="title-section">{t`Deliveries`}</h3>
      {deliveries.data?.results.length ? <ul className="grid gap-2">{deliveries.data.results.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-panel p-3">
        <div className="min-w-0 flex-1"><p className="font-semibold">{row.type}</p>
          <p className="text-sm text-muted"><RelativeTime date={row.created_at} />{` · ${row.attempts === 1 ? t`1 attempt` : t`${row.attempts} attempts`}`}{row.last_status_code ? ` · ${t`HTTP ${row.last_status_code}`}` : ""}{row.last_error ? ` · ${row.last_error}` : ""}</p></div>
        <StatusPill label={row.status === "delivered" ? t`Delivered` : row.status === "dead" ? t`Gave up` : t`Pending`} tone={row.status === "delivered" ? "success" : row.status === "dead" ? "danger" : "warn"} /></li>)}</ul>
        : <p className="text-sm text-muted">{deliveries.isLoading ? t`Loading…` : t`Nothing has been sent yet.`}</p>}
    </section> : null}
  </div>;
}
