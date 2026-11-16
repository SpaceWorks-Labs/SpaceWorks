import { t } from "@lingui/core/macro";

import { Callout, StatusPill } from "../../../../../components/ui";
import { stateLabel, stateTone, targetTypeLabel } from "./adapterCopy";
import type { AdapterSummary } from "./adaptersApi";
import { useTargetLabel } from "./bindingTargets";

export const KIOSK_CAPABILITY = "checkout.kiosk";
export const isKioskAdapter = (adapter: AdapterSummary) => adapter.adapter_kind === "kiosk" || adapter.capabilities.some(cap => cap.name === KIOSK_CAPABILITY);

/** Kiosk self-checkout terminals (child switch `machines.integrations.kiosk`): the bindings that serve `checkout.kiosk`. The terminal runs the normal self-checkout rules. */
export function AdapterKiosk({ makerspaceId, adapter }: { makerspaceId: number; adapter: AdapterSummary }) {
  const bindings = adapter.bindings.filter(row => row.capabilities.includes(KIOSK_CAPABILITY));
  const label = useTargetLabel(makerspaceId, bindings);
  return <div className="grid gap-4">
    <Callout size="inline" tone="warn" lead={t`The kiosk is only a terminal.`}
      body={t`Members still sign in, scan an eligible tool and upload their evidence photo; nothing here skips those rules. Sessions it starts show in the audit log.`} />
    {bindings.length ? <ul className="grid gap-3" aria-label={t`Kiosk bindings`}>{bindings.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-panel p-4">
      <div className="min-w-0 flex-1"><p className="title-section break-words">{label(row.target_type, row.machine_id, row.target_id, row.external_ref)}</p>
        <p className="text-sm text-muted">{targetTypeLabel(row.target_type)}{row.enabled ? "" : ` · ${t`Disabled`}`}</p></div>
      <StatusPill label={stateLabel(row.status?.state)} tone={stateTone(row.status?.state)} />
    </li>)}</ul> : <p className="text-sm text-muted">{t`No kiosk is bound yet. In Bindings, bind a space or storage location and tick the kiosk checkout capability.`}</p>}
  </div>;
}
