import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useContext, useId, useState, type ReactNode } from "react";

import { staffRequest } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { opsStatusLabel } from "./opsPresentation";
import { StaffListContext } from "./StaffListContext";

// Decision 216 item 13: independent facts shown side by side, each with its own source.
type Subject = { tenant: number; kind: "event" | "booking"; id: number };
type Counts = Record<string, number>;
type Section = { source: string } & Record<string, unknown>;
type Facts = Partial<Record<"registrations" | "attendance" | "presence" | "arrival" | "machine_sessions", Section>>;

export function RelatedFactsPanel(props: Subject) {
  const { actorId, makerspace } = useContext(StaffListContext);
  const modules = makerspace?.enabled_modules;
  const domain = props.kind === "event" ? "events" : "bookings";
  if (!actorId || makerspace?.id !== props.tenant || !modules?.includes(domain)) return null;
  // The server decides each section from its own module and authority; hidden sections are omitted.
  return <RelatedFacts key={JSON.stringify([actorId, props.tenant, props.kind, props.id])} {...props} actorId={actorId} />;
}

function RelatedFacts({ tenant, kind, id, actorId }: Subject & { actorId: number }) {
  const [open, setOpen] = useState(false);
  const path = `/admin/makerspace/${tenant}/related-facts/${kind === "event" ? "events" : "bookings"}/${id}`;
  const facts = useQuery({
    queryKey: ["related-facts", actorId, tenant, kind, id], enabled: open, retry: false, gcTime: 0,
    queryFn: ({ signal }) => staffRequest<Facts>(path, { signal }),
  });
  const panelId = useId();
  return <section className="grid gap-2" data-replay-block>
    <button className="desk-button w-fit" type="button" aria-expanded={open} aria-controls={panelId}
      onClick={() => setOpen(value => !value)}>{open ? t`Hide related activity` : t`View related activity`}</button>
    <div id={panelId} className="grid gap-2" hidden={!open}>{open ? <>
      {facts.isPending ? <p role="status">{t`Loading related activity…`}</p> : null}
      {facts.isError ? <p role="alert">{t`Related activity is unavailable for your access.`}</p> : null}
      {facts.data ? <div className="grid gap-3 sm:grid-cols-2">
        {facts.data.registrations ? <Card title={t`Registrations`} source={facts.data.registrations.source}>
          {Object.entries(facts.data.registrations.by_status as Counts).map(([status, n]) => <Row key={status} label={opsStatusLabel(status)} value={n} />)}
        </Card> : null}
        {facts.data.attendance ? <Card title={t`Event attendance`} source={facts.data.attendance.source}>
          <Row label={t`Attended registrations`} value={facts.data.attendance.attended_registrations} />
          <Row label={t`Check-in records`} value={facts.data.attendance.check_in_records} />
        </Card> : null}
        {facts.data.arrival ? <Card title={t`Booking arrival`} source={facts.data.arrival.source}>
          <Row label={t`Booking status`} value={opsStatusLabel(String(facts.data.arrival.booking_status ?? ""))} />
          <Row label={t`Arrived`} value={facts.data.arrival.arrived_at ? formatDateTime(String(facts.data.arrival.arrived_at)) : t`Not recorded`} />
          <Row label={t`Arrival reversals`} value={facts.data.arrival.arrival_reversals} />
        </Card> : null}
        {facts.data.presence ? <Card title={t`Presence check-ins in this window`} source={facts.data.presence.source}>
          <Row label={t`Sessions overlapping`} value={facts.data.presence.sessions_overlapping} />
          <Row label={t`People`} value={facts.data.presence.distinct_people} />
          {facts.data.presence.subject_person_presence ? <Row label={t`Booker present`}
            value={presenceLabel(facts.data.presence.subject_person_presence)} /> : null}
        </Card> : null}
        {facts.data.machine_sessions ? <Card title={t`Sessions on the booked machine`} source={facts.data.machine_sessions.source}>
          <Row label={String(facts.data.machine_sessions.machine_name)} value={facts.data.machine_sessions.sessions_overlapping} />
        </Card> : null}
      </div> : null}
    </> : null}</div>
  </section>;
}

function presenceLabel(value: unknown) {
  if (value === "withheld") return t`Hidden by presence privacy`;
  return value === "recorded" ? t`Recorded` : t`Not recorded`;
}

/** Each fact keeps its own provenance, named in operator language; an unknown one stays verbatim. */
function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    "events.EventRegistration": t`Event registrations`,
    "events.EventCheckInEvent": t`Event check-ins`,
    "bookings.BookingCheckInEvent": t`Booking arrivals`,
    "presence.PresenceSession": t`Presence check-ins`,
    "machines.MachineSession": t`Machine sessions`,
  };
  return labels[source] ?? source;
}

function Card({ title, source, children }: { title: string; source: string; children: ReactNode }) {
  const from = sourceLabel(source);
  return <article className="min-w-0 rounded-xl border border-line bg-panel p-3">
    <h4 className="font-semibold">{title}</h4>
    <dl className="grid gap-1 text-sm">{children}</dl>
    <p className="mt-2 text-xs text-muted">{t`Source: ${from}`}</p>
  </article>;
}

function Row({ label, value }: { label: string; value: unknown }) {
  return <div className="flex justify-between gap-3"><dt>{label}</dt><dd>{String(value ?? "")}</dd></div>;
}
