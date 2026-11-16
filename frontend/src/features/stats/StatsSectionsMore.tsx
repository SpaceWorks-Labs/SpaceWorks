import { t } from "@lingui/core/macro";
import { publicWidgetVisible, type PublicStatsCommunity, type PublicStatsEvents, type PublicStatsMetric, type PublicStatsVisibility } from "./api";
import { EmptyState, ListRow, StatCard } from "../../components/ui";
import { Section, StatTile, formatDate, formatNumber } from "./StatsParts";
import { formatCount } from "./StatsMetrics";

/** #170 sections beyond the original printing and lending blocks: machines, events and community. */
export function MachinesSection({ machines, metrics, period, visibility }: {
  machines: { usage_hours: number | null }; metrics: PublicStatsMetric[]; period: string; visibility?: PublicStatsVisibility;
}) {
  return <Section title={t`Machines`}>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {publicWidgetVisible(visibility, "machines.hours_all_time") && machines.usage_hours !== null
        ? <StatTile label={t`Machine hours all time`} value={`${formatNumber(machines.usage_hours)} h`} /> : null}
      {metrics.map(metric => <StatTile key={metric.key} label={`${metric.label}, ${period}`}
        value={`${formatNumber(metric.value ?? 0)} h`} />)}
    </div>
  </Section>;
}

export function EventsSection({ events, period, eventHref, visibility }: {
  events: PublicStatsEvents; period: string; eventHref: (token: string) => string; visibility?: PublicStatsVisibility;
}) {
  return <Section title={t`Events`}>
    <div className="grid gap-4 sm:grid-cols-3">
      {publicWidgetVisible(visibility, "events.upcoming") && events.upcoming_count !== null ? <StatCard label={t`Upcoming events`} value={formatCount(events.upcoming_count)} /> : null}
      {publicWidgetVisible(visibility, "events.held") && events.held !== null ? <StatCard label={t`Events held, ${period}`} value={formatCount(events.held)} /> : null}
      {publicWidgetVisible(visibility, "events.attendees") && events.attendees !== null ? <StatCard label={t`Attendees checked in, ${period}`} value={formatCount(events.attendees)} /> : null}
    </div>
    {publicWidgetVisible(visibility, "events.upcoming_list") ? <div><h3 className="title-section mb-3">{t`Coming up`}</h3>
      {events.upcoming.length ? <ul className="grid gap-3">{events.upcoming.map(event => <li key={event.public_token}>
        <ListRow title={event.title} href={eventHref(event.public_token)}
          identity={event.image_url ? { kind: "image", src: event.image_url } : { kind: "date", date: event.starts_at }}
          meta={formatDate(event.starts_at)} />
      </li>)}</ul> : <EmptyState message={t`No public events coming up. New events will appear here when they are published.`} />}
    </div> : null}
  </Section>;
}

const COMMUNITY_LABELS: [keyof PublicStatsCommunity, string, boolean][] = [
  ["active_members", "Active members", false], ["new_members", "New members", true],
  ["bookings", "Bookings", true], ["checkins", "Check-ins", true],
];

export function CommunitySection({ community, period, visibility }: { community: PublicStatsCommunity; period: string; visibility?: PublicStatsVisibility }) {
  const shown = COMMUNITY_LABELS.filter(([key]) => publicWidgetVisible(visibility, `community.${key}`) && community[key] !== null);
  return <Section title={t`Community`}>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {shown.map(([key, label, periodic]) => <StatCard key={key} label={periodic ? `${label}, ${period}` : label}
        value={formatCount(community[key])} />)}
    </div>
    <p className="text-sm text-muted">{t`Community counts below 3 show as “fewer than 3”.`}</p>
  </Section>;
}

