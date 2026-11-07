import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { KioskLayout } from "../../components/layouts";
import { MakerspaceMapLink } from "../../components/MakerspaceMapLink";
import { SupportContact } from "../../components/SupportContact";
import { ThemeToggle } from "../../components/ThemeToggle";
import { Card } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { PublicInventoryPage } from "../inventory/PublicInventoryPage";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { useStationConnection } from "./useStationConnection";

// The catalogue owns its data and cart; the desk supplies the makerspace identity, programme links,
// support contact and a two-column stage: products on the left, the request panel on the right.
export function PublicDeskKioskPage() {
  const { slug = "" } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug;
  const online = useStationConnection();
  const path = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const logo = bootstrap?.branding.logo_url || bootstrap?.makerspace.logo_url;
  // Catalogue is this page; every other programme link is one tap away, as the old catalogue header had.
  const programme = publicPageChrome(makerspaceSlug, name, path, bootstrap).nav.slice(1);
  return <PublicInventoryPage embedded={({ body, request }) => <KioskLayout
    context={{ identity: logo ? { kind: "image", src: logo } : undefined, title: name, subtitle: t`Public desk · Browse the catalogue and request what you need.` }}
    connection={{ online }} mode="work" state={{ status: "ready" }}
    headerActions={[...programme, { label: t`Open full catalogue`, href: path() }]}
    work={{ capture: <div className="text-lg [&_button]:min-h-12 [&_a]:min-h-12">{body}</div>,
      panel: <div className="grid gap-6"><Card>{request}</Card>
        <Card className="grid gap-4">
          <h2 className="title-panel">{t`Need a hand?`}</h2>
          <SupportContact branding={bootstrap?.branding} />
          <MakerspaceMapLink makerspace={bootstrap?.makerspace} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <ThemeToggle />
            <RouteLink className="text-sm text-muted underline hover:text-ink" href="/admin">{t`Staff sign-in`}</RouteLink>
          </div>
        </Card>
      </div> }} />} />;
}
