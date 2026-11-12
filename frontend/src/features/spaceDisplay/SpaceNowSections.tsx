import { t } from "@lingui/core/macro";
import type { TenantBootstrap } from "../../lib/api";
import { MakerspaceSection } from "../public/MakerspaceSection";
import { usePublicStats } from "../stats/api";
import { NOW_REFRESH_MS } from "./api";
import { usePublicNowConfig, type NowSection } from "./anthiasApi";
import { OpeningHoursList, StatsTiles } from "./DisplayPanelsMore";
import { EventsCalendarSection } from "./EventsCalendarSection";
import { HereNowSection } from "./HereNowSection";
import { MachinesNowSection } from "./MachinesNowSection";

const DEFAULT_ORDER: NowSection[] = ["here_now", "machines", "events"];

function PublicStatsNow({ slug }: { slug: string }) {
  const stats = usePublicStats(slug, NOW_REFRESH_MS / 1000).data;
  if (!stats) return null;
  const rows = (stats.headline.length ? stats.headline : stats.metrics).slice(0, 8);
  if (!rows.length) return null;
  return <MakerspaceSection id="in-numbers" title={t`In numbers`} subtitle={stats.period.label}>
    <StatsTiles tv={false} data={{ period: stats.period.label, metrics: rows.map((m) => ({ key: m.key, label: m.label, value: m.value, kind: m.kind, suppressed: m.suppressed })) }} />
  </MakerspaceSection>;
}

/**
 * Decisions 307a and 325a: the live sections of a space's public page, in the order and with the sections the
 * Space Manager chose. Each still sits behind its own module; the default (before anyone chooses) is the
 * original three. A failed config request falls back to that default rather than hiding the page.
 */
export function SpaceNowSections({ slug, bootstrap, path }: { slug: string; bootstrap: TenantBootstrap; path: (sub?: string) => string }) {
  const modules = new Set(bootstrap.modules);
  const config = usePublicNowConfig(slug).data;
  const order = config?.sections ?? DEFAULT_ORDER;
  const hours = bootstrap.makerspace.opening_hours as { weekly?: Record<string, { start: string; end: string }[]> } | undefined;
  return <>{order.map((section) => {
    if (section === "here_now") return <HereNowSection key={section} slug={slug} enabled={modules.has("presence")} />;
    if (section === "machines") return <MachinesNowSection key={section} slug={slug} enabled={modules.has("machines")} />;
    if (section === "events") return <EventsCalendarSection key={section} slug={slug} path={path} timeZone={bootstrap.makerspace.timezone ?? "UTC"} enabled={modules.has("events")} />;
    if (section === "public_stats") return <PublicStatsNow key={section} slug={slug} />;
    return hours?.weekly && Object.keys(hours.weekly).length
      ? <MakerspaceSection key={section} id="opening-hours" title={t`Opening hours`}><OpeningHoursList tv={false} data={hours} /></MakerspaceSection> : null;
  })}</>;
}
