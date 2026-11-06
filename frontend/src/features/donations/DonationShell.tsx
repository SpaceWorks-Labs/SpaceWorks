import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { useParams } from "react-router-dom";

import { PublicLayout } from "../../components/layouts";
import type { QueryState } from "../../components/ui";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { useTenantBootstrap } from "../inventory/usePublicInventory";

/** The space this donation route belongs to: the tenant domain's own, or `/m/:slug`. */
export function useDonationSpace() {
  const { slug } = useParams();
  const tenant = useTenant();
  const space = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const bootstrapQuery = useTenantBootstrap(space, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  return { slug: space, bootstrap, path: useTenantPath(space) };
}

/** Public chrome for every giving page: the space's brand, nav and footer, one narrow column. */
export function DonationShell({ title, subtitle, state, children }: {
  title: string; subtitle?: string; state: QueryState; children: ReactNode;
}) {
  const { slug, bootstrap, path } = useDonationSpace();
  const brandStyle = useTenantBranding(bootstrap);
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || slug;
  return <div style={brandStyle}>
    <PublicLayout {...publicPageChrome(slug, name, path, bootstrap)} width="narrow" state={state}
      header={{ eyebrow: name, title, subtitle }} breadcrumb={[{ label: name, href: path() }, { label: t`Support` }]}>
      {children}
    </PublicLayout>
  </div>;
}
