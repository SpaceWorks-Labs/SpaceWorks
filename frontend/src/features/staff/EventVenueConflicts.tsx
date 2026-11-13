import { t } from "@lingui/core/macro";

import { StatusPill } from "../../components/ui";
import { formatLocale } from "../../lib/format";

/** Decision 216: a room outage, machine repair or closure meeting a linked reservation. Never applied. */
export type VenueConflict = {
  code: "room_out_of_service" | "room_outage_warning" | "machine_under_repair" | "space_closed";
  severity: "block" | "warning";
  starts_at?: string; ends_at?: string; reason?: string;
};

function copy(code: VenueConflict["code"], machine: boolean) {
  switch (code) {
    case "room_out_of_service":
      return [machine ? t`Room out of service during this booking` : t`Room out of service during this event`,
        t`The room refuses new bookings for this time. Move the event, or replace the booking once it is cancelled.`];
    case "room_outage_warning":
      return [t`Room outage reported during this event`, t`Bookings are still allowed. Check the room is usable before the event.`];
    case "machine_under_repair":
      return [t`Machine under repair during this booking`, t`Reschedule the machine booking in Bookings, or replace it once it is cancelled.`];
    case "space_closed":
      return [t`Space closed during part of this time`, t`It is outside opening hours or a closure day. Staff events may still run; make sure the space can be opened.`];
    default:
      return [t`Venue update pending`, ""];
  }
}

function span(row: VenueConflict) {
  if (!row.starts_at || !row.ends_at) return "";
  const format = (value: string) => new Date(value).toLocaleString(formatLocale());
  return `${format(row.starts_at)} – ${format(row.ends_at)}`;
}

/** The conflicts the server reported, one line each; nothing here changes the booking or event. */
export function VenueConflictList({ conflicts, machine = false }: { conflicts?: VenueConflict[]; machine?: boolean }) {
  if (!conflicts?.length) return null;
  return <ul className="grid gap-2" aria-label={t`Venue conflicts`}>
    {conflicts.map((row, index) => {
      const [title, hint] = copy(row.code, machine);
      const when = span(row);
      return <li key={`${row.code}-${row.starts_at ?? index}`} className="grid gap-1 rounded-md border border-line p-2 text-sm"
        role={row.severity === "block" ? "alert" : "status"}>
        <span className="flex flex-wrap items-center gap-2">
          <StatusPill tone={row.severity === "block" ? "danger" : "warn"} label={row.severity === "block" ? t`Blocked` : t`Warning`} />
          <strong>{title}</strong></span>
        {when ? <span>{when}</span> : null}
        {row.reason ? <span>{t`Reason: ${row.reason}`}</span> : null}
        {hint ? <span className="text-muted">{hint}</span> : null}
      </li>;
    })}
  </ul>;
}
