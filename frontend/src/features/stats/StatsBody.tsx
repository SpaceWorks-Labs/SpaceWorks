import type { PublicStatsResponse, StatsSectionKey } from "./api";
import { CurrentLoansSection, HardwareSection, PrintingSection } from "./StatsSections";
import { CommunitySection, EventsSection, MachinesSection } from "./StatsSectionsMore";
import { HeadlineRow, PeriodTiles, metricsFor } from "./StatsMetrics";

/** The shown sections in the Space Manager's order (#170); a hidden one never arrives. */
export function StatsBody({ stats, eventHref }: { stats: PublicStatsResponse; eventHref: (token: string) => string }) {
  const period = stats.period.label;
  const section = (key: StatsSectionKey) => {
    if (key === "events" && stats.events) return <EventsSection events={stats.events} period={period} eventHref={eventHref} />;
    if (key === "machines" && stats.machines) return <MachinesSection machines={stats.machines} period={period}
      metrics={metricsFor(stats.metrics, "machines")} />;
    if (key === "printing" && stats.printing) return <div className="grid gap-4">
      <PeriodTiles metrics={metricsFor(stats.metrics, "printing")} period={period} />
      <PrintingSection printing={stats.printing} /></div>;
    if (key === "lending" && stats.hardware) return <div className="grid gap-8">
      <PeriodTiles metrics={metricsFor(stats.metrics, "lending")} period={period} />
      <HardwareSection hardware={stats.hardware} /><CurrentLoansSection loans={stats.current_loans ?? []} /></div>;
    if (key === "community" && stats.community) return <CommunitySection community={stats.community} period={period} />;
    return null;
  };
  return <div className="grid gap-8">
    <HeadlineRow metrics={stats.headline} period={period} />
    {stats.sections.map(key => <div key={key}>{section(key)}</div>)}
  </div>;
}

export function isEmptyStats(stats: PublicStatsResponse) {
  return stats.sections.length === 0;
}
