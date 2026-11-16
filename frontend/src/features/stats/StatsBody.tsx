import type { PublicStatsResponse, StatsSectionKey } from "./api";
import { publicWidgetVisible } from "./api";
import { CurrentLoansSection, HardwareSection, PrintingSection } from "./StatsSections";
import { CommunitySection, EventsSection, MachinesSection } from "./StatsSectionsMore";
import { HeadlineRow, PeriodTiles, metricsFor } from "./StatsMetrics";

/** The shown sections in the Space Manager's order (#170); a hidden one never arrives. */
export function StatsBody({ stats, eventHref }: { stats: PublicStatsResponse; eventHref: (token: string) => string }) {
  const period = stats.period.label;
  const metrics = stats.metrics.filter(metric => publicWidgetVisible(stats.visibility, metric.key));
  const section = (key: StatsSectionKey) => {
    if (key === "events" && stats.events) return <EventsSection events={stats.events} period={period} eventHref={eventHref} visibility={stats.visibility} />;
    if (key === "machines" && stats.machines) return <MachinesSection machines={stats.machines} period={period}
      metrics={metricsFor(metrics, "machines")} visibility={stats.visibility} />;
    if (key === "printing" && stats.printing) return <div className="grid gap-4">
      <PeriodTiles metrics={metricsFor(metrics, "printing")} period={period} />
      <PrintingSection printing={stats.printing} visibility={stats.visibility} /></div>;
    if (key === "lending") return <div className="grid gap-8">
      <PeriodTiles metrics={metricsFor(metrics, "lending")} period={period} />
      {stats.hardware ? <HardwareSection hardware={stats.hardware} visibility={stats.visibility} /> : null}
      {publicWidgetVisible(stats.visibility, "lending.current_loans") && stats.current_loans !== null
        ? <CurrentLoansSection loans={stats.current_loans} /> : null}</div>;
    if (key === "community" && stats.community) return <CommunitySection community={stats.community} period={period} visibility={stats.visibility} />;
    return null;
  };
  return <div className="grid gap-8">
    <HeadlineRow metrics={stats.headline.filter(metric => publicWidgetVisible(stats.visibility, metric.key))} period={period} />
    {stats.sections.map(key => <div key={key}>{section(key)}</div>)}
  </div>;
}

export function isEmptyStats(stats: PublicStatsResponse) {
  return stats.sections.length === 0;
}
