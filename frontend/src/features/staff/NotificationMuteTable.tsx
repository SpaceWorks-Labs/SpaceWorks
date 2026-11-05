import { DataTable } from "../../components/ui";
import { MATRIX_TOGGLE_CELL, STICKY_FIRST_COLUMN } from "./matrixColumns";
import type { MuteChange, RuleCatalogEntry, RuleMute } from "./notificationRuleTypes";

export function NotificationMuteTable({ entry, mutes, emailEnabled, disabledMessageId, pending, onChange }: {
  entry: RuleCatalogEntry; mutes: RuleMute[]; emailEnabled: boolean; disabledMessageId: string;
  pending: boolean; onChange: (change: MuteChange) => void;
}) {
  return <DataTable data={entry.targets.map(target => ({ target }))} getRowId={row => row.target} columns={[
    { key: "target", header: "Target", className: `font-semibold ${STICKY_FIRST_COLUMN}`, render: row => targetLabel(row.target) },
    ...entry.events.map(eventName => ({ key: eventName, header: humanize(eventName), className: MATRIX_TOGGLE_CELL, render: ({ target }: { target: string }) => {
      const checked = mutes.some(mute => mute.target === target && mute.stream === entry.stream
        && mute.event === eventName && mute.audience === entry.audience);
      return <label className="inline-flex min-h-11 min-w-11 items-center justify-center">
        <input aria-describedby={!emailEnabled ? disabledMessageId : undefined}
          aria-label={`${checked ? "Unmute" : "Mute"} ${targetLabel(target)} ${humanize(eventName)}`}
          type="checkbox" checked={checked} disabled={pending || !emailEnabled}
          onChange={event => onChange({ target, stream: entry.stream, event: eventName, audience: entry.audience, muted: event.target.checked })} />
      </label>;
    } })),
  ]} caption={`Muted ${humanize(entry.stream)} emails by recipient and event. Checked means muted.`} emptyTitle="No recipient mutes yet." />;
}
function humanize(value: string) {
  const label = value.replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}
function targetLabel(target: string) {
  return ({ requester: "Requesters", space_manager: "Space managers", inventory_manager: "Inventory managers",
    machine_manager: "Machine managers", event_manager: "Event managers", booking_manager: "Booking managers",
    handover: "Handover", technician: "Technicians", shop_manager: "Shop managers" }[target] ?? humanize(target));
}
