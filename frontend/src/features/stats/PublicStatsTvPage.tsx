import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { PageMetadata } from "../../components/PageMetadata";
import { AnimatedLogoMark } from "../../components/brand/AnimatedLogoMark";
import { LayoutFrame, QueryContent } from "../../components/layouts/LayoutFrame";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useTenant } from "../../lib/tenant";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { publicErrorState } from "../inventory/publicErrorState";
import { publicWidgetVisible, usePublicStats, type PublicStatsResponse, type StatsSectionKey } from "./api";
import { HeadlineRow, formatMetric, metricsFor } from "./StatsMetrics";
import { formatDate } from "./StatsParts";

const SECTION_TITLES: Record<StatsSectionKey, string> = {
  events: t`Events`, machines: t`Machines`, printing: t`Printing`, lending: t`Inventory`, community: t`Community`,
};

/**
 * #170 TV mode: a full-screen board for a lobby screen. No navigation, large type, and it
 * refetches on the Space Manager's interval. Updates swap numbers in place with no motion at
 * all (nothing scrolls, rotates or fades), so it is safe under reduced motion by construction.
 */
export function PublicStatsTvPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const [refresh, setRefresh] = useState<number>();
  const query = usePublicStats(makerspaceSlug, refresh);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const logo = bootstrap?.branding.logo_url || bootstrap?.makerspace.logo_url;
  const stats = query.data;
  useEffect(() => { setRefresh(stats?.tv.enabled ? stats.tv.refresh_seconds : undefined); }, [stats]);

  return <div style={brandStyle} className="min-h-dvh bg-bg text-ink">
    <PageMetadata title={t`${name} in numbers`} description={t`Live public stats for ${name}.`} path={window.location.pathname} siteName={name} noindex />
    <LayoutFrame standalone width="wide" className="py-10">
      <header className="mb-10 flex flex-wrap items-center gap-6">
        {logo ? <img src={logo} alt={name} className="h-16 w-auto max-w-[min(60vw,20rem)] object-contain" />
          : <AnimatedLogoMark variant="symbol" size={64} />}
        <div className="min-w-0 flex-[1_1_14rem]">
          <h1 className={logo ? "sr-only" : "break-words font-accent text-3xl font-semibold sm:text-4xl xl:text-5xl"}>{name}</h1>
          {stats ? <p className="mt-2 text-2xl text-muted">{stats.period.label}</p> : null}
        </div>
        {query.dataUpdatedAt ? <p className="text-xl tabular-nums text-muted">
          {t`Updated ${new Date(query.dataUpdatedAt).toLocaleTimeString(formatLocale(), { hour: "2-digit", minute: "2-digit" })}`}</p> : null}
      </header>
      <QueryContent state={query.isLoading ? { status: "loading" } : query.isError
        ? publicErrorState(query.error, { surface: "stats", missing: t`Stats are not available for this makerspace.` }, () => { void query.refetch(); })
        : { status: "ready" }}
        isEmpty={Boolean(stats && !stats.tv.enabled)}
        empty={{ message: t`TV mode is off for this makerspace. A Space Manager can turn it on in Settings › Public stats.` }}>
        {stats ? <TvBoard stats={stats} /> : null}
      </QueryContent>
    </LayoutFrame>
  </div>;
}

function TvBoard({ stats }: { stats: PublicStatsResponse }) {
  const metrics = stats.metrics.filter(metric => publicWidgetVisible(stats.visibility, metric.key));
  const selected = stats.headline.filter(metric => publicWidgetVisible(stats.visibility, metric.key));
  const headline = selected.length ? selected : metrics.slice(0, 4);
  const rest = metrics.filter(metric => !headline.some(row => row.key === metric.key));
  return <div className="grid gap-10">
    <HeadlineRow metrics={headline} period={stats.period.label} size="tv" />
    <div className="grid gap-8 xl:grid-cols-2">
      {stats.sections.map(key => {
        const metrics = metricsFor(rest, key);
        const events = key === "events" && publicWidgetVisible(stats.visibility, "events.upcoming_list") ? stats.events?.upcoming.slice(0, 4) ?? [] : [];
        if (!metrics.length && !events.length) return null;
        return <section key={key} aria-labelledby={`tv-${key}`} className="rounded-2xl border border-line bg-panel p-8">
          <h2 id={`tv-${key}`} className="text-3xl font-semibold">{SECTION_TITLES[key]}</h2>
          <dl className="mt-6 grid gap-6 sm:grid-cols-2">{metrics.map(metric => <div key={metric.key} className="min-w-0">
            <dt className="text-xl text-muted">{metric.label}</dt>
            <dd className="mt-1 break-words font-display text-heading font-semibold tabular-nums">{formatMetric(metric)}</dd>
          </div>)}</dl>
          {events.length ? <ul className="mt-6 grid gap-3 text-2xl">{events.map(event => <li key={event.public_token}
            className="flex flex-wrap justify-between gap-4"><span className="min-w-0 break-words font-semibold">{event.title}</span>
            <span className="tabular-nums text-muted">{formatDate(event.starts_at)}</span></li>)}</ul> : null}
        </section>;
      })}
    </div>
  </div>;
}
