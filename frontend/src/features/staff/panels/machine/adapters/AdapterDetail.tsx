import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { DetailLayout } from "../../../../../components/layouts";
import { RelativeTime, StatusPill } from "../../../../../components/ui";
import { opsQueryState } from "../../../opsPresentation";
import { AdapterBindings } from "./AdapterBindings";
import { AdapterDiagnostics, AdapterOfflineConfig } from "./AdapterDiagnostics";
import { AdapterKiosk, isKioskAdapter } from "./AdapterKiosk";
import { AdapterLogs } from "./AdapterLogs";
import { AdapterArtifacts, AdapterDetections, AdapterTelemetry } from "./AdapterMedia";
import { AdapterStatus } from "./AdapterStatus";
import { AdapterWebhook } from "./AdapterWebhook";
import { AdapterWatch } from "./AdapterWatch";
import { ShelfPointer } from "./ShelfPointer";
import { adapterErrorMessage, capabilityLabel } from "./adapterCopy";
import { adapterKeys, adaptersApi, type AdapterSwitches } from "./adaptersApi";

export function AdapterDetail({ makerspaceId, adapterId, switches, onBack }: {
  makerspaceId: number; adapterId: string; switches: AdapterSwitches; onBack: () => void;
}) {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const adapter = useQuery({ queryKey: adapterKeys.detail(makerspaceId, adapterId), queryFn: () => adaptersApi.detail(adapterId), refetchInterval: 10_000 });
  const revoke = useMutation({ mutationFn: () => adaptersApi.revoke(adapterId), onSuccess: () => { void client.invalidateQueries({ queryKey: adapterKeys.root(makerspaceId) }); } });
  const data = adapter.data;
  const caps = (name: string) => (data?.bindings ?? []).filter(binding => binding.capabilities.includes(name));
  const hasVideo = switches.video && (caps("media.snapshot").length > 0 || caps("media.stream").length > 0);
  const tabs = [{ key: "status", label: t`Status and controls`, href: "#" }, { key: "bindings", label: t`Bindings`, href: "#" },
    ...(caps("locate.calibrate").length || caps("locate.indicate").length ? [{ key: "pointer", label: t`Shelf pointer`, href: "#" }] : []),
    ...(hasVideo ? [{ key: "watch", label: t`Watch`, href: "#" }] : []),
    ...(switches.artifacts && caps("artifact.upload").length ? [{ key: "artifacts", label: t`Timelapses and previews`, href: "#" }] : []),
    ...(switches.detections && caps("detection.report").length ? [{ key: "detections", label: t`Detections`, href: "#" }] : []),
    ...(switches.history && caps("telemetry.history").length ? [{ key: "telemetry", label: t`Charts`, href: "#" }] : []),
    ...(switches.diagnostics && caps("diagnostics").length ? [{ key: "diagnostics", label: t`Diagnostics`, href: "#" }] : []),
    { key: "offline", label: t`Offline and config`, href: "#" },
    ...(switches.kiosk && data && isKioskAdapter(data) ? [{ key: "kiosk", label: t`Kiosk`, href: "#" }] : []), { key: "webhook", label: t`Webhook`, href: "#" }, { key: "logs", label: t`Logs`, href: "#" }];
  const active = tabs.find(tab => tab.key === params.get("adapter_view"))?.key ?? "status";
  const revoked = data?.status === "revoked";
  const online = data?.online ?? false;
  return <>
    <DetailLayout back={{ label: t`All adapters`, onClick: onBack }} title={data?.name ?? t`Device adapter`}
      state={opsQueryState(adapter, "this adapter")}
      status={data ? <StatusPill label={revoked ? t`Revoked` : online ? t`Online` : t`Offline`} tone={revoked ? "danger" : online ? "success" : "warn"} /> : undefined}
      meta={data ? [data.adapter_kind ? data.adapter_kind.replace(/_/g, " ") : t`Not introduced yet`, data.vendor || null, data.software_version ? `v${data.software_version}` : null,
        data.offline_since ? <>{t`Offline since `}<RelativeTime date={data.offline_since} /></> : data.last_seen_at ? <>{t`Last seen `}<RelativeTime date={data.last_seen_at} /></> : t`Never seen`].filter(Boolean) as ReactNode[] : undefined}
      tabs={tabs} activeTab={active} onTabChange={key => setParams(current => { const next = new URLSearchParams(current); next.set("adapter_view", key); return next; })}
      banner={revoke.isError ? { size: "inline", tone: "danger", lead: t`Couldn't revoke.`, body: adapterErrorMessage(revoke.error) }
        : revoked ? { size: "inline", tone: "danger", lead: t`This adapter is revoked.`, body: t`It can no longer connect. Enrol a new bridge to replace it.` } : undefined}
      main={data ? <div className="grid gap-6">
        {data.capabilities.length ? <p className="text-sm text-muted">{t`Declares: `}{data.capabilities.map(cap => capabilityLabel(cap)).join(", ")}</p> : null}
        {active === "status" ? <AdapterStatus makerspaceId={makerspaceId} adapter={data} disabled={revoked} /> : null}
        {active === "bindings" ? <AdapterBindings makerspaceId={makerspaceId} adapter={data} disabled={revoked} switches={switches} /> : null}
        {active === "pointer" ? <ShelfPointer makerspaceId={makerspaceId} adapter={data} /> : null}
        {active === "watch" ? <AdapterWatch makerspaceId={makerspaceId} adapter={data} recordingEnabled={switches.recording} switches={switches} /> : null}
        {active === "artifacts" ? <AdapterArtifacts makerspaceId={makerspaceId} adapter={data} /> : null}
        {active === "detections" ? <AdapterDetections makerspaceId={makerspaceId} adapter={data} /> : null}
        {active === "telemetry" ? <AdapterTelemetry makerspaceId={makerspaceId} adapter={data} /> : null}
        {active === "diagnostics" ? <AdapterDiagnostics makerspaceId={makerspaceId} adapter={data} bundles={Boolean(switches.artifacts)} /> : null}
        {active === "offline" ? <AdapterOfflineConfig makerspaceId={makerspaceId} adapter={data} /> : null}
        {active === "kiosk" ? <AdapterKiosk makerspaceId={makerspaceId} adapter={data} /> : null}
        {active === "webhook" ? <AdapterWebhook makerspaceId={makerspaceId} adapterId={adapterId} /> : null}
        {active === "logs" ? <AdapterLogs makerspaceId={makerspaceId} adapter={data} /> : null}
      </div> : null}
      danger={data && !revoked ? [{ title: t`Revoke this adapter`, consequence: t`The bridge stops working at once. Its history stays in the logs. This cannot be undone.`,
        action: { label: t`Revoke adapter`, pending: revoke.isPending, onClick: () => revoke.mutate(),
          confirm: { title: t`Revoke ${data.name}?`, message: t`The bridge will be cut off immediately. To use that hardware again you will enrol a new bridge and bind it again.`, confirmLabel: t`Revoke adapter` } } }] : undefined} />
  </>;
}
