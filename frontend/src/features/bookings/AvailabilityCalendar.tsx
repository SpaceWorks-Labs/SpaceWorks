import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { EmptyState } from "../../components/ui/EmptyState";
import { useMemo, useState } from "react";

import { usePublicAvailability } from "./publicBookingsApi";

const WINDOW_DAYS = 14;

function windowDates(offset: number) {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() + offset * WINDOW_DAYS);
  const end = new Date(start);
  end.setDate(end.getDate() + WINDOW_DAYS);
  return { startsAt: start.toISOString(), endsAt: end.toISOString() };
}

function rangeLabel(startsAt: string, endsAt: string) {
  const format = new Intl.DateTimeFormat(formatLocale(), { dateStyle: "medium" });
  const inclusiveEnd = new Date(new Date(endsAt).getTime() - 1);
  return `${format.format(new Date(startsAt))} – ${format.format(inclusiveEnd)}`;
}

function intervalLabel(startsAt: string, endsAt: string, timeZone?: string) {
  const format = new Intl.DateTimeFormat(formatLocale(), { dateStyle: "medium", timeStyle: "short", timeZone });
  return `${format.format(new Date(startsAt))} – ${format.format(new Date(endsAt))}`;
}

export function AvailabilityCalendar({ makerspaceSlug, publicToken }: {
  makerspaceSlug: string;
  publicToken: string;
}) {
  const [offset, setOffset] = useState(0);
  const window = useMemo(() => windowDates(offset), [offset]);
  const availability = usePublicAvailability(makerspaceSlug, publicToken, window.startsAt, window.endsAt);

  return (
    <section className="rounded-lg border border-brand bg-brand-soft p-4" aria-labelledby={"availability-" + publicToken}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 id={"availability-" + publicToken} className="title-section">{t`Published availability`}</h3>
          <p className="eyebrow mt-1">{rangeLabel(window.startsAt, window.endsAt)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="desk-button-ghost" type="button" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 1))}>{t`Previous 14 days`}</button>
          <button className="desk-button-ghost" type="button" onClick={() => setOffset((value) => value + 1)}>{t`Next 14 days`}</button>
        </div>
      </div>
      {availability.isLoading ? <p className="mt-3 text-sm text-muted" aria-live="polite">{t`Checking confirmed bookings...`}</p> : null}
      {availability.error ? (
        <div className="mt-3" role="alert">
          <p className="text-sm text-danger">{t`Availability could not be checked. This does not mean the space is free.`}</p>
          <button className="desk-button-ghost mt-2" type="button" onClick={() => availability.refetch()}>{t`Retry`}</button>
        </div>
      ) : null}
      {availability.data?.opening_intervals ? <div className="mt-3 text-sm text-muted">
        <p className="font-semibold">{t`Opening times (${availability.data.timezone})`}</p>
        {availability.data.opening_intervals.length === 0 ? <p>{t`The makerspace is closed in this window.`}</p> : <ul>{availability.data.opening_intervals.map((interval) => <li key={interval.starts_at}>{intervalLabel(interval.starts_at, interval.ends_at, availability.data.timezone)}</li>)}</ul>}
      </div> : null}
      {/* Closed time is already the gaps in the opening times above; list only the other blocks,
          and only where the room publishes its availability (decision 219c; the server enforces it). */}
      {availability.data?.availability != null && availability.data.unavailable?.some((block) => block.kind === "unavailable") ? (
        <ul className="mt-3 grid gap-2" aria-label={t`Unavailable times`}>
          {(availability.data.unavailable ?? []).filter((block) => block.kind === "unavailable").map((block) => (
            <li className="break-words rounded-lg border border-warn bg-warn-soft px-3 py-2 text-sm text-ink" key={"unavailable" + block.starts_at + block.ends_at}>
              <span className="mr-2 font-semibold">{t`Unavailable`}</span>
              <time className="tabular-nums" dateTime={block.starts_at}>{intervalLabel(block.starts_at, block.ends_at, availability.data?.timezone)}</time>
            </li>
          ))}
        </ul>
      ) : null}
      {availability.data?.availability === null ? (
        <p className="mt-3 text-sm text-muted">{t`Availability is not published. You may still submit your selected time for the makerspace to check.`}</p>
      ) : null}
      {availability.data?.availability?.length === 0 ? (
        <EmptyState message={t`No confirmed bookings are published in this window.`} />
      ) : null}
      {availability.data?.availability?.length ? (
        <ul className="mt-3 grid gap-2">
          {/* A pending event hold reads like an unavailable block, labelled, and never names anyone. */}
          {availability.data.availability.map((interval) => interval.tentative ? (
            <li className="break-words rounded-lg border border-warn bg-warn-soft px-3 py-2 text-sm text-ink" key={interval.starts_at + interval.ends_at}>
              <span className="mr-2 font-semibold">{t`Tentative`}</span>
              <time className="tabular-nums" dateTime={interval.starts_at}>{intervalLabel(interval.starts_at, interval.ends_at, availability.data?.timezone)}</time>
            </li>
          ) : (
            <li className="break-words rounded-lg border border-success bg-success-soft px-3 py-2 text-sm text-ink" key={interval.starts_at + interval.ends_at}>
              <time className="tabular-nums" dateTime={interval.starts_at}>{intervalLabel(interval.starts_at, interval.ends_at, availability.data?.timezone)}</time>
              {interval.booker_name !== null ? <span className="ml-2 font-semibold">{interval.booker_name}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
