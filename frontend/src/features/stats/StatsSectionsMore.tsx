import type { PublicStatsCommunity, PublicStatsEvents, PublicStatsMetric } from "./api";
import { EmptyState, ListRow, StatCard } from "../../components/ui";
import { Section, StatTile, formatDate, formatNumber } from "./StatsParts";
import { formatCount } from "./StatsMetrics";

/** #170 sections beyond the original printing and lending blocks: machines, events and community. */
export function MachinesSection({ machines, metrics, period }: {
  machines: { usage_hours: number }; metrics: PublicStatsMetric[]; period: string;
}) {
  return <Section title="Machines">
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile label="Machine hours all time" value={`${formatNumber(machines.usage_hours)} h`} />
      {metrics.map(metric => <StatTile key={metric.key} label={`${metric.label}, ${period}`}
        value={`${formatNumber(metric.value ?? 0)} h`} />)}
    </div>
  </Section>;
}

export function EventsSection({ events, period, eventHref }: {
  events: PublicStatsEvents; period: string; eventHref: (token: string) => string;
}) {
  return <Section title="Events">
    <div className="grid gap-4 sm:grid-cols-3">
      <StatCard label="Upcoming events" value={formatCount(events.upcoming_count)} />
      <StatCard label={`Events held, ${period}`} value={formatCount(events.held)} />
      <StatCard label={`Attendees checked in, ${period}`} value={formatCount(events.attendees)} />
    </div>
    <div><h3 className="title-section mb-3">Coming up</h3>
      {events.upcoming.length ? <ul className="grid gap-3">{events.upcoming.map(event => <li key={event.public_token}>
        <ListRow title={event.title} href={eventHref(event.public_token)}
          identity={event.image_url ? { kind: "image", src: event.image_url } : { kind: "date", date: event.starts_at }}
          meta={formatDate(event.starts_at)} />
      </li>)}</ul> : <EmptyState message="No public events coming up. New events will appear here when they are published." />}
    </div>
  </Section>;
}

const COMMUNITY_LABELS: [keyof PublicStatsCommunity, string, boolean][] = [
  ["active_members", "Active members", false], ["new_members", "New members", true],
  ["bookings", "Bookings", true], ["checkins", "Check-ins", true],
];

export function CommunitySection({ community, period }: { community: PublicStatsCommunity; period: string }) {
  const shown = COMMUNITY_LABELS.filter(([key]) => community[key] !== null);
  return <Section title="Community">
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {shown.map(([key, label, periodic]) => <StatCard key={key} label={periodic ? `${label}, ${period}` : label}
        value={formatCount(community[key])} />)}
    </div>
    <p className="text-sm text-muted">Counts only, never names. Any count below 3 shows as “fewer than 3”.</p>
  </Section>;
}

