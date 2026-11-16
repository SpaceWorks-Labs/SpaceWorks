import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Callout, Field, RelativeTime, StatusPill } from "../../../../../components/ui";
import { ArtifactGallery } from "./ArtifactGallery";
import { adapterErrorMessage } from "./adapterCopy";
import type { AdapterSummary, Binding } from "./adaptersApi";
import { mediaApi, mediaKeys, type ConfigVersion } from "./adaptersMediaApi";
import { useTargetLabel } from "./bindingTargets";
import { BoxArt } from "../../../../../components/BoxSpinner";

const healthTone = (health: string | undefined) => health === "ok" ? "success" as const : health === "degraded" ? "warn" as const : health === "failing" ? "danger" as const : "neutral" as const;
export const healthLabel = (health: string | undefined) => health === "ok" ? t`Healthy` : health === "degraded" ? t`Degraded` : health === "failing" ? t`Failing` : t`Not reported`;

/** Adapter health, firmware and a log bundle on request (decision 321e). The bundle is private, seven days, and opening it is audited. */
export function AdapterDiagnostics({ makerspaceId, adapter, bundles }: { makerspaceId: number; adapter: AdapterSummary; bundles: boolean }) {
  const client = useQueryClient();
  const rows = adapter.bindings.filter(row => row.capabilities.includes("diagnostics"));
  const label = useTargetLabel(makerspaceId, rows);
  const [picked, setPicked] = useState("");
  const binding: Binding | undefined = rows.find(row => row.id === picked) ?? rows[0];
  const ask = useMutation({ mutationFn: () => mediaApi.requestLogBundle(binding!.id), onSuccess: () => { void client.invalidateQueries({ queryKey: ["device-adapters", "artifacts"] }); } });
  const list = useQuery({ queryKey: mediaKeys.artifacts(binding?.id ?? "", "log_bundle"), queryFn: () => mediaApi.artifacts(binding!.id, "log_bundle"), enabled: Boolean(binding) && bundles, refetchInterval: ask.isSuccess ? 10_000 : false });
  const dropped = adapter.telemetry_dropped_7d ?? 0;
  return <div className="grid gap-4">
    {dropped > 0 ? <Callout size="inline" tone="warn" lead={t`${dropped.toLocaleString()} telemetry samples dropped: limit reached`}
      body={t`In the last 7 days. This space reached its telemetry limit, so new readings were not stored. Ask the platform operator to raise it.`} /> : null}
    <dl className="grid gap-2 rounded-2xl border border-line bg-panel p-4 text-sm sm:grid-cols-2">
      <div><dt className="text-muted">{t`Health`}</dt><dd><StatusPill label={healthLabel(adapter.health)} tone={healthTone(adapter.health)} /></dd></div>
      <div><dt className="text-muted">{t`Last health report`}</dt><dd>{adapter.health_at ? <RelativeTime date={adapter.health_at} /> : t`Never`}</dd></div>
      <div><dt className="text-muted">{t`Software`}</dt><dd>{adapter.software_version || t`Not reported`}</dd></div>
      <div><dt className="text-muted">{t`Firmware`}</dt><dd>{adapter.firmware || t`Not reported`}</dd></div>
    </dl>
    {binding ? <section className="grid gap-3" aria-label={t`Log bundle`}>
      <h3 className="title-section">{t`Log bundle`}</h3>
      <p className="text-sm text-muted">{t`Ask the adapter to send its recent logs. The file is private to staff, kept for 7 days and capped at 10 MB. Opening it is recorded in the audit log.`}</p>
      {rows.length > 1 ? <Field label={t`Target`}><select className="desk-input" value={binding.id} onChange={event => setPicked(event.target.value)}>
        {rows.map(row => <option key={row.id} value={row.id}>{label(row.target_type, row.machine_id, row.target_id, row.external_ref)}</option>)}</select></Field> : null}
      <button type="button" className="desk-button-primary justify-self-start" disabled={ask.isPending || !bundles} onClick={() => ask.mutate()}>{ask.isPending ? <><BoxArt size={16} mono />{t`Asking…`}</> : t`Request log bundle`}</button>
      {ask.isSuccess ? <p role="status" className="text-sm text-muted">{t`Requested. It appears below when the adapter uploads it.`}</p> : null}
      {ask.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(ask.error)}</p> : null}
      {bundles ? <ArtifactGallery rows={list.data?.results ?? []} getUrl={mediaApi.artifactUrl} /> : null}
    </section> : <p className="text-sm text-muted">{t`No target on this adapter reports diagnostics.`}</p>}
  </div>;
}

const parseConfig = (text: string): Record<string, unknown> | null => {
  try { const value: unknown = JSON.parse(text); return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null; } catch { return null; }
};
const ackLabel = (row: ConfigVersion) => row.ack_outcome === "applied" ? t`Applied` : row.ack_outcome === "rejected" ? t`Rejected` : t`Waiting for the adapter`;

/** The offline access cache status of each binding (never the digests) and the versioned config pushed to the adapter (decision 321f, g). */
export function AdapterOfflineConfig({ makerspaceId, adapter }: { makerspaceId: number; adapter: AdapterSummary }) {
  const client = useQueryClient();
  const caches = adapter.bindings.filter(row => row.capabilities.includes("access.cache"));
  const label = useTargetLabel(makerspaceId, caches);
  const [text, setText] = useState("{}");
  const versions = useQuery({ queryKey: mediaKeys.configs(adapter.id), queryFn: () => mediaApi.configVersions(adapter.id) });
  const push = useMutation({ mutationFn: (config: Record<string, unknown>) => mediaApi.pushConfig(adapter.id, config), onSuccess: () => { void client.invalidateQueries({ queryKey: mediaKeys.configs(adapter.id) }); } });
  const config = parseConfig(text);
  return <div className="grid gap-6">
    <section className="grid gap-3" aria-label={t`Offline access`}>
      <h3 className="title-section">{t`Offline access`}</h3>
      <p className="text-sm text-muted">{t`A short-lived signed list of card digests lets a door or machine decide while offline. It holds no PINs and no personal data, and a revoked card disappears at the next sync.`}</p>
      {caches.length ? <ul className="grid gap-2">{caches.map(row => <li key={row.id} className="rounded-xl border border-line bg-panel p-3 text-sm">
        <p className="font-medium">{label(row.target_type, row.machine_id, row.target_id, row.external_ref)}</p>
        {row.offline_cache ? <p className="text-muted">{t`${row.offline_cache.entry_count} cards · last synced`} <RelativeTime date={row.offline_cache.issued_at} />
          {" · "}{new Date(row.offline_cache.expires_at).getTime() < Date.now() ? t`expired` : t`expires`} <span className="lowercase"><RelativeTime date={row.offline_cache.expires_at} /></span></p> : <p className="text-muted">{t`Never synced.`}</p>}
      </li>)}</ul> : <p className="text-sm text-muted">{t`No target on this adapter uses an offline cache.`}</p>}
    </section>
    <section className="grid gap-3" aria-label={t`Config versions`}>
      <h3 className="title-section">{t`Config versions`}</h3>
      <p className="text-sm text-muted">{t`Settings the adapter fetches and confirms. Do not put passwords or tokens here; keep those on the adapter.`}</p>
      <form className="grid gap-2" onSubmit={event => { event.preventDefault(); if (config) push.mutate(config); }}>
        <Field label={t`New config (JSON object)`} hint={config ? undefined : t`That is not a JSON object.`}><textarea className="desk-input font-mono" rows={5} value={text} onChange={event => setText(event.target.value)} aria-invalid={!config} /></Field>
        <button type="submit" className="desk-button-primary justify-self-start" disabled={!config || push.isPending}>{push.isPending ? <><BoxArt size={16} mono />{t`Pushing…`}</> : t`Push new version`}</button>
      </form>
      {push.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(push.error)}</p> : null}
      <ul className="grid gap-2" aria-label={t`Pushed versions`}>{(versions.data ?? []).map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-panel p-3 text-sm">
        <strong>{t`Version ${row.version}`}</strong><StatusPill label={ackLabel(row)} tone={row.ack_outcome === "applied" ? "success" : row.ack_outcome === "rejected" ? "danger" : "warn"} />
        <span className="text-muted"><RelativeTime date={row.created_at} /></span>{row.ack_detail ? <span>{row.ack_detail}</span> : null}</li>)}</ul>
    </section>
  </div>;
}
