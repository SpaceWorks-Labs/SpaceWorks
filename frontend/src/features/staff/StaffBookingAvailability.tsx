import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import { staffRequest } from "../../lib/api";
import { formatLocale } from "../../lib/format";

type Label = { kind: "booking" | "event" | "reserved"; event_id?: number; title?: string; event_status?: string };
/** `tentative`: a pending booking that holds its slot because it is an event's venue (decision 223 (m)). */
type Span = { booking_id: number; starts_at: string; ends_at: string; label: Label; tentative?: boolean };
/** Decision 216: the room's calendar from the Bookings owner, read-only. Submit re-verifies. */
export type StaffAvailability = {
  space_id: number; timezone: string; range_starts_at: string; range_ends_at: string;
  opening_intervals: { starts_at: string; ends_at: string }[];
  busy: Span[]; pending: Span[];
  requested: { within_rules: boolean; rule_detail: string; conflict: boolean; holds_room_on_create: boolean };
};

/** An ISO instant as a `datetime-local` value in the browser's zone. */
export function toLocalInput(iso?: string | null) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function iso(value: string) {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date.toISOString() : null;
}

function span(row: { starts_at: string; ends_at: string }) {
  const format = (value: string) => new Date(value).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
  return `${format(row.starts_at)} – ${format(row.ends_at)}`;
}

function labelText(label: Label) {
  if (label.kind === "event") {
    return label.event_status === "cancelled" ? t`Event (cancelled): ${label.title ?? ""}` : t`Event: ${label.title ?? ""}`;
  }
  return label.kind === "reserved" ? t`Reserved` : t`Booked`;
}

function verdict(requested: StaffAvailability["requested"]) {
  if (requested.conflict) {
    return requested.holds_room_on_create
      ? t`This time overlaps a confirmed booking. The booking will be refused.`
      : t`This time overlaps a confirmed booking. Approval will be refused while it does.`;
  }
  return requested.within_rules ? t`The room is free at this time.` : "";
}

/** Free/busy for the chosen room over the local day(s) of the chosen window. */
export function StaffBookingAvailability({ spaceId, start, end }: { spaceId: number; start: string; end: string }) {
  const startsAt = iso(start);
  const endsAt = iso(end);
  const path = startsAt && endsAt && endsAt > startsAt
    ? `/admin/spaces/${spaceId}/bookings/availability/?${new URLSearchParams({ starts_at: startsAt, ends_at: endsAt })}` : null;
  // A plain effect, not a query: the staff booking form renders outside any QueryClient.
  const [result, setResult] = useState<{ path: string; data: StaffAvailability | null } | null>(null);
  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    staffRequest<StaffAvailability>(path, { signal: controller.signal })
      .then(data => setResult({ path, data }))
      .catch(() => { if (!controller.signal.aborted) setResult({ path, data: null }); });
    return () => controller.abort();
  }, [path]);
  if (path === null) return null;
  if (result?.path !== path) return <p className="text-sm text-muted" role="status">{t`Checking room availability…`}</p>;
  const data = result.data;
  if (!data) return <p className="text-sm text-muted">{t`Room availability is unavailable. The booking is still checked when you submit.`}</p>;
  const message = verdict(data.requested);
  return <section className="grid gap-2 rounded-md border border-line p-2 text-sm sm:col-span-2" aria-label={t`Room availability`}>
    <p className="text-xs text-muted">{t`Room calendar in your local time (the space uses ${data.timezone}). Confirmed bookings hold the room, and so does a pending booking that is an event's venue.`}</p>
    {message ? <p role={data.requested.conflict ? "alert" : "status"}>{message}</p> : null}
    {!data.requested.within_rules && data.requested.rule_detail ? <p role="alert">{data.requested.rule_detail}</p> : null}
    <div><strong>{t`Open`}</strong>
      {data.opening_intervals.length ? <ul>{data.opening_intervals.map(row => <li key={row.starts_at}>{span(row)}</li>)}</ul>
        : <p>{t`Closed for these days.`}</p>}</div>
    <div><strong>{t`Booked`}</strong>
      {data.busy.length ? <ul aria-label={t`Booked times`}>{data.busy.map(row => <li key={row.booking_id}>{span(row)} · {labelText(row.label)}{row.tentative ? ` · ${t`held tentatively, awaiting approval`}` : ""}</li>)}</ul>
        : <p>{t`No confirmed bookings on these days.`}</p>}</div>
    {data.pending.length ? <div><strong>{t`Awaiting approval (does not hold the room)`}</strong>
      <ul aria-label={t`Pending bookings`}>{data.pending.map(row => <li key={row.booking_id}>{span(row)} · {labelText(row.label)}</li>)}</ul></div> : null}
  </section>;
}
