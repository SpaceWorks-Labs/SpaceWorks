import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Field, RelativeTime, StatusPill } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type AdapterCommand, type AdapterEvent, type AdapterSummary } from "./adaptersApi";
import { AccessLog, UsageLog } from "./AdapterLogLists";
import { useTargetLabel } from "./bindingTargets";
import { LogoLoader } from "../../../../../components/LogoLoader";

type Kind = "commands" | "events" | "access" | "usage";

const commandTone = (status: AdapterCommand["status"]) => status === "succeeded" ? "success" as const : status === "failed" || status === "expired" ? "danger" as const : "warn" as const;

/** Commands sent, events received, access decisions and usage for one bridge: newest first, up to 50 each, staff only. */
export function AdapterLogs({ makerspaceId, adapter }: { makerspaceId: number; adapter: AdapterSummary }) {
  const [kind, setKind] = useState<Kind>("commands");
  const [binding, setBinding] = useState("");
  const [text, setText] = useState("");
  const label = useTargetLabel(makerspaceId, adapter.bindings);
  const nameOf = (id: string | null) => { const row = adapter.bindings.find(item => item.id === id); return row ? label(row.target_type, row.machine_id, row.target_id, row.external_ref) : t`Adapter`; };
  const commands = useQuery({ queryKey: adapterKeys.commands(makerspaceId, adapter.id), queryFn: () => adaptersApi.commands(adapter.id), enabled: kind === "commands" });
  const events = useQuery({ queryKey: adapterKeys.events(makerspaceId, adapter.id), queryFn: () => adaptersApi.events(adapter.id), enabled: kind === "events" });
  const needle = text.trim().toLowerCase();
  const sameBinding = (row: { binding: string | null }) => !binding || row.binding === binding;
  const commandRows = (commands.data ?? []).filter(row => sameBinding(row) && (!needle || `${row.capability} ${row.command} ${row.status} ${row.result_code}`.toLowerCase().includes(needle)));
  const eventRows = (events.data ?? []).filter(row => sameBinding(row)
    && (!needle || `${row.event_type} ${row.capability} ${JSON.stringify(row.data)}`.toLowerCase().includes(needle)));
  const query = kind === "commands" ? commands : events;
  const lists = kind === "access" || kind === "usage";
  const kinds: { key: Kind; label: string }[] = [{ key: "commands", label: t`Commands` }, { key: "events", label: t`Events` },
    { key: "access", label: t`Access decisions` }, { key: "usage", label: t`Usage` }];
  return <div className="grid gap-4">
    <div className="flex flex-wrap gap-2" role="group" aria-label={t`Log type`}>{kinds.map(row => <button key={row.key} type="button" aria-pressed={kind === row.key}
      className={kind === row.key ? "desk-button-primary" : "desk-button"} onClick={() => setKind(row.key)}>{row.label}</button>)}</div>
    {kind === "access" ? <AccessLog makerspaceId={makerspaceId} adapter={adapter} nameOf={nameOf} /> : kind === "usage" ? <UsageLog makerspaceId={makerspaceId} adapter={adapter} nameOf={nameOf} /> : null}
    {lists ? null : <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Target`}><select className="desk-input" value={binding} onChange={event => setBinding(event.target.value)}>
        <option value="">{t`All targets`}</option>{adapter.bindings.map(row => <option key={row.id} value={row.id}>{nameOf(row.id)}</option>)}</select></Field>
      <Field label={t`Search`}><input className="desk-input" type="search" value={text} onChange={event => setText(event.target.value)} /></Field>
    </div>}
    {!lists && query.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(query.error)}</p> : null}
    {!lists && query.isLoading ? <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" /> : null}
    {lists ? null : kind === "commands" ? <ul className="grid gap-2" aria-label={t`Commands`}>{commandRows.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-panel p-3">
      <div className="min-w-0 flex-1"><p className="font-semibold break-words">{row.command} <span className="font-normal text-muted">· {row.capability}</span></p>
        <p className="text-sm text-muted">{nameOf(row.binding)} · <RelativeTime date={row.created_at} />{row.result_code ? ` · ${row.result_code}` : ""}{row.attempts > 1 ? ` · ${t`${row.attempts} attempts`}` : ""}</p></div>
      <StatusPill label={row.status} tone={commandTone(row.status)} /></li>)}</ul>
      : <ul className="grid gap-2" aria-label={kinds.find(row => row.key === kind)?.label}>{eventRows.map((row: AdapterEvent) => <li key={row.id} className="grid gap-1 rounded-2xl border border-line bg-panel p-3">
        <p className="font-semibold break-words">{row.event_type} <span className="font-normal text-muted">· {row.capability}</span></p>
        <p className="text-sm text-muted">{nameOf(row.binding)} · <RelativeTime date={row.observed_at} /></p>
        {Object.keys(row.data).length ? <p className="text-xs text-muted [overflow-wrap:anywhere]">{JSON.stringify(row.data)}</p> : null}</li>)}</ul>}
    {!lists && !query.isLoading && (kind === "commands" ? !commandRows.length : !eventRows.length) ? <p className="text-sm text-muted">{t`Nothing matches.`}</p> : null}
  </div>;
}
