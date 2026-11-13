import { t } from "@lingui/core/macro";
import { MakerspaceSection } from "../public/MakerspaceSection";
import { useMachinesNow, type MachineNowStatus } from "./api";

export const machineStatusLabel = (status: MachineNowStatus): string =>
  ({ in_use: t`In use`, free: t`Free`, out_of_service: t`Out of service` })[status];

const TONE: Record<MachineNowStatus, string> = {
  in_use: "border-warn bg-warn-soft text-warn-ink", free: "border-success bg-success-soft text-success-ink",
  out_of_service: "border-line bg-surface text-muted",
};

/** The status is a word as well as a colour, so it reads without colour vision. Never who is using one. */
export function MachineChip({ status }: { status: MachineNowStatus }) {
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${TONE[status]}`}>{machineStatusLabel(status)}</span>;
}

export function MachinesNowSection({ slug, enabled }: { slug: string; enabled: boolean }) {
  const query = useMachinesNow(slug, enabled);
  if (!enabled || !query.data || query.data.items.length === 0) return null;
  const { in_use: inUse, free, out_of_service: out, items } = query.data;
  return <MakerspaceSection id="machines-now" title={t`Machines now`}
    subtitle={t`${free} free · ${inUse} in use · ${out} out of service`}>
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => <li key={`${item.name}-${item.type}`} className="flex items-center justify-between gap-3 rounded-xl border border-line bg-panel p-3">
        <span className="min-w-0"><span className="block break-words font-semibold">{item.name}</span><span className="block text-sm text-muted">{item.type}</span></span>
        <MachineChip status={item.status} />
      </li>)}
    </ul>
  </MakerspaceSection>;
}
