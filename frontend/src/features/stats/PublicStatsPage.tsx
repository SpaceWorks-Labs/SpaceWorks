import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { publicErrorState } from "../inventory/publicErrorState";
import { usePublicStats } from "./api";
import { StatsBody, isEmptyStats } from "./StatsBody";

export function PublicStatsPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(
    makerspaceSlug,
    tenant.mode === "central",
  );
  const statsQuery = usePublicStats(makerspaceSlug);
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const displayName =
    bootstrap?.branding.display_name ||
    bootstrap?.makerspace.name ||
    formatSlug(makerspaceSlug) ||
    "Makerspace";
  const stats = statsQuery.data;

  return <div style={brandStyle}><PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)}
    header={{ eyebrow: stats ? t`Live stats · ${stats.period.label}` : t`Live stats`, title: t`${displayName} in numbers`,
      subtitle: t`Counts only, never names. Small numbers show as “fewer than 3”.`,
      primary: { label: t`Browse catalogue`, href: tenantPath() },
      secondary: stats?.tv.enabled ? { label: t`Open TV mode`, href: tenantPath("stats/tv") } : undefined }}
    state={statsQuery.isLoading ? { status: "loading" } : statsQuery.isError ? publicErrorState(statsQuery.error, { noun: "Public stats", missing: "Stats not available. This makerspace has its public stats page turned off, or it may not exist." }, () => { void statsQuery.refetch(); }) : { status: "ready" }}
    isEmpty={Boolean(stats && isEmptyStats(stats))} empty={{ message: t`Nothing to show yet. Stats fill in as people borrow, print and visit.` }}>
    {stats ? <StatsBody stats={stats} eventHref={token => tenantPath(`events/${token}`)} /> : null}
  </PublicLayout></div>;
}
