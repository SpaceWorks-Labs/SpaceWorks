import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Field, RelativeTime, StatusPill } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type AdapterSummary, type Page } from "./adaptersApi";
import { LogoLoader } from "../../../../../components/LogoLoader";

const day = (value: string, end = false) => value ? `${value}T${end ? "23:59:59" : "00:00:00"}Z` : "";

function Pager({ page, data, setPage }: { page: number; data?: Page<unknown>; setPage: (page: number) => void }) {
  if (!data || (!data.previous && !data.next)) return null;
  return <div className="flex items-center gap-2"><button type="button" className="desk-button" disabled={!data.previous} onClick={() => setPage(page - 1)}>{t`Previous`}</button>
    <span className="text-sm text-muted">{t`Page ${page}`}</span>
    <button type="button" className="desk-button" disabled={!data.next} onClick={() => setPage(page + 1)}>{t`Next`}</button></div>;
}

function Filters({ adapter, binding, setBinding, since, setSince, until, setUntil, children }: { adapter: AdapterSummary; binding: string; setBinding: (v: string) => void;
  since: string; setSince: (v: string) => void; until: string; setUntil: (v: string) => void; children: React.ReactNode }) {
  return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <Field label={t`Target`}><select className="desk-input" value={binding} onChange={event => setBinding(event.target.value)}>
      <option value="">{t`All targets`}</option>{adapter.bindings.map(row => <option key={row.id} value={row.id}>{row.external_ref || row.target_id || row.target_type}</option>)}</select></Field>
    {children}
    <Field label={t`From`}><input className="desk-input" type="date" value={since} onChange={event => setSince(event.target.value)} /></Field>
    <Field label={t`To`}><input className="desk-input" type="date" value={until} onChange={event => setUntil(event.target.value)} /></Field>
  </div>;
}

/** Every access decision of this adapter (allowed or denied, with the reason), from the server's own log, newest first. */
export function AccessLog({ makerspaceId, adapter, nameOf }: { makerspaceId: number; adapter: AdapterSummary; nameOf: (id: string | null) => string }) {
  const [f, setF] = useState({ binding: "", allowed: "", reason: "", credential_type: "", since: "", until: "" });
  const [page, setPage] = useState(1);
  const set = (patch: Partial<typeof f>) => { setF({ ...f, ...patch }); setPage(1); };
  const query = new URLSearchParams({ page: String(page), ...(f.binding ? { binding: f.binding } : {}), ...(f.allowed ? { allowed: f.allowed } : {}), ...(f.reason.trim() ? { reason: f.reason.trim() } : {}),
    ...(f.credential_type ? { credential_type: f.credential_type } : {}), ...(f.since ? { since: day(f.since) } : {}), ...(f.until ? { until: day(f.until, true) } : {}) }).toString();
  const rows = useQuery({ queryKey: adapterKeys.access(makerspaceId, adapter.id, query), queryFn: () => adaptersApi.accessDecisions(adapter.id, query) });
  return <div className="grid gap-4">
    <Filters adapter={adapter} binding={f.binding} setBinding={binding => set({ binding })} since={f.since} setSince={since => set({ since })} until={f.until} setUntil={until => set({ until })}>
      <Field label={t`Decision`}><select className="desk-input" value={f.allowed} onChange={event => set({ allowed: event.target.value })}>
        <option value="">{t`Allowed and denied`}</option><option value="true">{t`Allowed`}</option><option value="false">{t`Denied`}</option></select></Field>
      <Field label={t`Credential`}><select className="desk-input" value={f.credential_type} onChange={event => set({ credential_type: event.target.value })}>
        <option value="">{t`Any`}</option><option value="card_qr">{t`Member card`}</option><option value="nfc">{t`NFC tag`}</option><option value="pin">{t`PIN`}</option></select></Field>
      <Field label={t`Reason`}><input className="desk-input" type="search" value={f.reason} onChange={event => set({ reason: event.target.value })} /></Field>
    </Filters>
    {rows.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(rows.error)}</p> : null}
    {rows.isLoading ? <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" /> : null}
    <ul className="grid gap-2" aria-label={t`Access decisions`}>{rows.data?.results.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-panel p-3">
      <div className="min-w-0 flex-1"><p className="font-semibold break-words">{row.reason.replace(/_/g, " ")}</p>
        <p className="text-sm text-muted">{nameOf(row.binding)} · {row.credential_type} · {row.member !== null ? t`Member #${row.member}` : t`Unknown credential`} · <RelativeTime date={row.created_at} /></p></div>
      <StatusPill label={row.allowed ? t`Allowed` : t`Denied`} tone={row.allowed ? "success" : "danger"} /></li>)}</ul>
    {rows.isSuccess && !rows.data.results.length ? <p className="text-sm text-muted">{t`Nothing matches.`}</p> : null}
    <Pager page={page} data={rows.data} setPage={setPage} />
  </div>;
}

/** The usage records the adapter reported: session length, idle time and how each ended. */
export function UsageLog({ makerspaceId, adapter, nameOf }: { makerspaceId: number; adapter: AdapterSummary; nameOf: (id: string | null) => string }) {
  const [f, setF] = useState({ binding: "", outcome: "", since: "", until: "" });
  const [page, setPage] = useState(1);
  const set = (patch: Partial<typeof f>) => { setF({ ...f, ...patch }); setPage(1); };
  const query = new URLSearchParams({ page: String(page), ...(f.binding ? { binding: f.binding } : {}), ...(f.outcome.trim() ? { outcome: f.outcome.trim() } : {}),
    ...(f.since ? { since: day(f.since) } : {}), ...(f.until ? { until: day(f.until, true) } : {}) }).toString();
  const rows = useQuery({ queryKey: adapterKeys.usage(makerspaceId, adapter.id, query), queryFn: () => adaptersApi.usage(adapter.id, query) });
  return <div className="grid gap-4">
    <Filters adapter={adapter} binding={f.binding} setBinding={binding => set({ binding })} since={f.since} setSince={since => set({ since })} until={f.until} setUntil={until => set({ until })}>
      <Field label={t`Outcome`}><input className="desk-input" type="search" value={f.outcome} onChange={event => set({ outcome: event.target.value })} /></Field>
    </Filters>
    {rows.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(rows.error)}</p> : null}
    {rows.isLoading ? <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" /> : null}
    <ul className="grid gap-2" aria-label={t`Usage`}>{rows.data?.results.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-panel p-3">
      <div className="min-w-0 flex-1"><p className="font-semibold break-words">{nameOf(row.binding)}</p>
        <p className="text-sm text-muted"><RelativeTime date={row.started_at} />{row.active_minutes !== null ? ` · ${t`${row.active_minutes} min active`}` : ""}{row.idle_minutes !== null ? ` · ${t`${row.idle_minutes} min idle`}` : ""}{row.error_code ? ` · ${row.error_code}` : ""}</p></div>
      <StatusPill label={row.outcome} tone={row.error_code ? "danger" : "neutral"} /></li>)}</ul>
    {rows.isSuccess && !rows.data.results.length ? <p className="text-sm text-muted">{t`Nothing matches.`}</p> : null}
    <Pager page={page} data={rows.data} setPage={setPage} />
  </div>;
}
