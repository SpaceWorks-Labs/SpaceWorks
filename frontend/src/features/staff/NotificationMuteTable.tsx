import { t } from "@lingui/core/macro";
import { DataTable } from "../../components/ui";
import { MATRIX_TOGGLE_CELL, STICKY_FIRST_COLUMN } from "./matrixColumns";
import type { MuteChange, RuleCatalogEntry, RuleMute } from "./notificationRuleTypes";
import { notificationEventLabel } from "../notifications/notificationEventLabels";

export function NotificationMuteTable({ entry, mutes, emailEnabled, disabledMessageId, pending, onChange }: {
  entry: RuleCatalogEntry; mutes: RuleMute[]; emailEnabled: boolean; disabledMessageId: string;
  pending: boolean; onChange: (change: MuteChange) => void;
}) {
  return <DataTable data={entry.targets.map(target => ({ target }))} getRowId={row => row.target} columns={[
    { key: "target", header: t`Recipient`, className: `font-semibold ${STICKY_FIRST_COLUMN}`, render: row => targetLabel(row.target) },
    ...entry.events.map(eventName => ({ key: eventName, header: notificationEventLabel(eventName), className: MATRIX_TOGGLE_CELL, render: ({ target }: { target: string }) => {
      const checked = mutes.some(mute => mute.target === target && mute.stream === entry.stream
        && mute.event === eventName && mute.audience === entry.audience);
      return <label className="inline-flex min-h-11 min-w-11 items-center justify-center">
        <input aria-describedby={!emailEnabled ? disabledMessageId : undefined}
          aria-label={checked ? t`Unmute ${targetLabel(target)}: ${notificationEventLabel(eventName)}` : t`Mute ${targetLabel(target)}: ${notificationEventLabel(eventName)}`}
          type="checkbox" checked={checked} disabled={pending || !emailEnabled}
          onChange={event => onChange({ target, stream: entry.stream, event: eventName, audience: entry.audience, muted: event.target.checked })} />
      </label>;
    } })),
  ]} caption={t`Muted ${muteStreamLabel(entry.stream)} emails by recipient and event. Checked means muted.`} emptyTitle={t`No recipient mutes yet.`} />;
}
/** Translated name of a notification mute stream; "hardware" is the Inventory area. */
export function muteStreamLabel(stream: string): string {
  switch (stream) {
    case "hardware": return t`Inventory`;
    case "printing": return t`Printing`;
    case "events": return t`Events`;
    case "bookings": return t`Bookings`;
    case "members": return t`Members`;
    case "presence": return t`Presence`;
    default: return humanize(stream);
  }
}
function humanize(value: string) {
  const label = value.replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}
function targetLabel(target: string) {
  return ({ requester: t`Requesters`, space_manager: t`Space managers`, inventory_manager: t`Inventory managers`,
    machine_manager: t`Machine managers`, event_manager: t`Event managers`, booking_manager: t`Booking managers`,
    handover: t`Handover`, technician: t`Technicians`, shop_manager: t`Shop managers`, fundraising: t`Fundraising` } as Record<string, string>)[target] ?? humanize(target);
}
