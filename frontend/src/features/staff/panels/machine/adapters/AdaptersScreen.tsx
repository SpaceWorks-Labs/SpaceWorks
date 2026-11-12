import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../../../../components/layouts";
import { ListRow, RelativeTime, StatusPill } from "../../../../../components/ui";
import { ScreenHelp } from "../../../../help/HelpLink";
import { opsQueryState } from "../../../opsPresentation";
import { AdapterDetail } from "./AdapterDetail";
import { AdapterCredentials } from "./AdapterCredentials";
import { AdapterEnroll } from "./AdapterEnroll";
import { AdapterTypeProfiles } from "./AdapterTypeProfiles";
import { isKioskAdapter } from "./AdapterKiosk";
import { adapterKeys, adaptersApi, type AdapterSummary, type AdapterSwitches } from "./adaptersApi";

function connection(adapter: AdapterSummary) {
  if (adapter.status === "revoked") return { label: t`Revoked`, tone: "danger" as const };
  if (adapter.status === "pending") return { label: t`Waiting to connect`, tone: "warn" as const };
  return adapter.online ? { label: t`Online`, tone: "success" as const } : { label: t`Offline`, tone: "warn" as const };
}

/** The Machines console "Device adapters" screen (`?view=adapters`, decision 312): bridges, credentials, and each bridge's detail. */
export function AdaptersScreen({ makerspaceId, switches, onBack }: {
  makerspaceId: number; switches: AdapterSwitches; onBack: () => void;
}) {
  const [params, setParams] = useSearchParams();
  const [enrolling, setEnrolling] = useState(false);
  const adapters = useQuery({ queryKey: adapterKeys.list(makerspaceId), queryFn: () => adaptersApi.list(makerspaceId), refetchInterval: 30_000 });
  const selected = params.get("adapter");
  const asked = params.get("adapter_tab");
  const tab = asked === "types" ? "types" : switches.access && asked === "credentials" ? "credentials" : "bridges";
  const change = (patch: Record<string, string | null>) => setParams(current => {
    const next = new URLSearchParams(current);
    for (const [key, value] of Object.entries(patch)) { if (value === null) next.delete(key); else next.set(key, value); }
    return next;
  });
  if (selected) return <AdapterDetail makerspaceId={makerspaceId} adapterId={selected} switches={switches}
    onBack={() => change({ adapter: null, adapter_view: null })} />;
  const rows = adapters.data?.results ?? [];
  return <>
    <ListLayout header={{ title: t`Device adapters`, subtitle: t`Bridges that connect printers, shelf pointers, doors and cameras to Space Works.`,
      primary: { label: t`Enrol a bridge`, icon: "Plus", onClick: () => setEnrolling(true) }, secondary: { label: t`All machines`, onClick: onBack } }}
      callout={{ size: "inline", tone: "warn", lead: t`Staff only.`, body: t`Shelf positions, camera views and access credentials never appear on public pages.` }}
      tabs={[{ key: "bridges", label: t`Bridges`, href: "#" }, ...(switches.access ? [{ key: "credentials", label: t`Credentials`, href: "#" }] : []), { key: "types", label: t`Machine types`, href: "#" }]}
      activeTab={tab} onTabChange={key => change({ adapter_tab: key === "bridges" ? null : key })}
      state={tab !== "bridges" ? { status: "ready" } : opsQueryState(adapters, "device adapters")}
      isEmpty={tab === "bridges" && rows.length === 0}
      empty={{ message: t`No bridges yet. Enrol one to connect your first device.`, action: { label: t`Enrol a bridge`, onClick: () => setEnrolling(true) } }}
      body={tab === "types" ? { kind: "rows", rows: <AdapterTypeProfiles makerspaceId={makerspaceId} /> } : tab === "credentials" ? { kind: "rows", rows: <AdapterCredentials makerspaceId={makerspaceId} /> }
        : { kind: "rows", rows: rows.map(adapter => {
          const state = connection(adapter);
          const bound = adapter.bindings.length;
          return <ListRow key={adapter.id} title={adapter.name} onClick={() => change({ adapter: adapter.id })}
            identity={{ kind: "icon", icon: "Settings", tone: "accent" }}
            meta={<>{adapter.adapter_kind ? adapter.adapter_kind.replace(/_/g, " ") : t`Not introduced yet`}{switches.kiosk && isKioskAdapter(adapter) ? ` · ${t`Kiosk`}` : ""}
              {" · "}{adapter.capabilities.length ? plural(adapter.capabilities.length, { one: "# capability", other: "# capabilities" }) : t`no capabilities declared`}
              {" · "}{bound ? plural(bound, { one: "# bound target", other: "# bound targets" }) : t`nothing bound`}
              {" · "}{adapter.offline_since ? <>{t`Offline since `}<RelativeTime date={adapter.offline_since} /></> : adapter.last_seen_at ? <>{t`Last seen `}<RelativeTime date={adapter.last_seen_at} /></> : t`Never seen`}</>}
            right={<StatusPill label={state.label} tone={state.tone} />} />;
        }) }} />
    <ScreenHelp screen="machines.adapters" />
    {enrolling ? <AdapterEnroll makerspaceId={makerspaceId} onClose={() => setEnrolling(false)} /> : null}
  </>;
}
