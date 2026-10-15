import { useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { publicErrorState } from "../inventory/publicErrorState";
import { usePublicStats, type PublicStatsResponse } from "./api";
import { CurrentLoansSection, HardwareSection, PrintingSection } from "./StatsSections";

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

  return <div style={brandStyle}><PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)}
    header={{ eyebrow: "Live stats", title: `${displayName} in numbers`, subtitle: "Updated live from the public catalogue.", primary: { label: "Browse catalogue", href: tenantPath() } }}
    state={statsQuery.isLoading ? { status: "loading" } : statsQuery.isError ? publicErrorState(statsQuery.error, { noun: "Public stats", missing: "Stats not available. This makerspace has its public stats page turned off, or it may not exist." }, () => { void statsQuery.refetch(); }) : { status: "ready" }}
    isEmpty={Boolean(statsQuery.data && isEmptyStats(statsQuery.data))} empty={{ message: "Nothing to show yet. Stats fill in as people borrow and print." }}>
    {statsQuery.data ? <div className="grid gap-8">
      {statsQuery.data.printing ? <PrintingSection printing={statsQuery.data.printing} /> : null}
      <HardwareSection hardware={statsQuery.data.hardware} /><CurrentLoansSection loans={statsQuery.data.current_loans} />
    </div> : null}
  </PublicLayout></div>;
}

function isEmptyStats(stats: PublicStatsResponse) {
  return (
    stats.printing === null &&
    stats.hardware.library.library_size === 0 &&
    stats.hardware.most_popular.length === 0 &&
    stats.hardware.tools_out.length === 0 &&
    stats.hardware.recently_added.length === 0 &&
    stats.current_loans.length === 0
  );
}
