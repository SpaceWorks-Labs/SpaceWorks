import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getAccessToken, refreshAccessToken } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";

export type MemberSession = "restoring" | "authenticated" | "anonymous";

/** Restores a member session once so checkout knows whether to ask a guest for an email code. */
export function useMemberSession() {
  const [session, setSession] = useState<MemberSession>(() => getAccessToken() ? "authenticated" : "restoring");
  useEffect(() => {
    let active = true;
    if (!getAccessToken()) {
      void refreshAccessToken().then(restored => { if (active) setSession(restored ? "authenticated" : "anonymous"); })
        .catch(() => { if (active) setSession("anonymous"); });
    }
    return () => { active = false; };
  }, []);
  return [session, setSession] as const;
}

/** The space a shop page belongs to, its public chrome and its brand, on central and single-site installs. */
export function useShopSpace() {
  const { slug = "" } = useParams();
  const tenant = useTenant();
  const tenantSlug = tenant.mode === "single" ? tenant.slug : slug;
  const path = useTenantPath(tenantSlug);
  const bootstrapQuery = useTenantBootstrap(tenantSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(tenantSlug) || "Makerspace";
  // A tenant-prefixed link on a single-site install must name this site.
  const valid = tenant.mode !== "single" || !slug || slug === tenant.slug;
  return { slug: valid ? tenantSlug : "", path, bootstrap, brandStyle, name,
    chrome: publicPageChrome(tenantSlug, name, path, bootstrap) };
}
