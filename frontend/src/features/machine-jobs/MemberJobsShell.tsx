import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import type { TenantBootstrap } from "../../lib/api";
import { logout } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { MemberPortalTabs } from "../members/MemberPortalTabs";
import { forgetOfflineMemberData } from "../members/memberCard/offlineCard";
import { useMemberIdentity } from "./useMemberIdentity";

export type MemberJobsContext = {
  slug: string; makerspaceId: number | undefined; path: (part?: string) => string; ready: boolean; bootstrapError: boolean;
  features?: string[];
};

/**
 * The member shell around the machine-job pages: the same sidebar as the member area, the
 * session restored once, and the sign-in panel instead of the page for a signed-out visitor.
 */
export function MemberJobsShell({ children }: { children: (context: MemberJobsContext) => ReactNode }) {
  const { slug } = useParams();
  const tenant = useTenant();
  const client = useQueryClient();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const path = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap: TenantBootstrap | null | undefined = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const member = useMemberIdentity();
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || "Makerspace";
  const logo = bootstrap?.branding.logo_url || bootstrap?.makerspace.logo_url || undefined;
  if (member.signedOut) return <div style={brandStyle}><MemberAuthPanel makerspaceSlug={makerspaceSlug} eyebrow={t`Your machine jobs`}
    tenantBrand={bootstrap ? { name, logo } : undefined} onAuthenticated={() => { void member.identity.refetch(); }} /></div>;
  const memberHome = path("member");
  return <div style={brandStyle}>
    <MemberPortalTabs modules={bootstrap?.modules ?? []} features={bootstrap?.features} active="overview"
      space={{ id: bootstrap?.makerspace.id, slug: makerspaceSlug || undefined }}
      workspace={bootstrap ? { name: bootstrap.makerspace.name, subtitle: t`Member area`,
        avatar: logo ? { kind: "image", src: logo } : { kind: "avatar", name: bootstrap.makerspace.name, seed: makerspaceSlug }, locked: true } : undefined}
      user={{ name: member.identity.data?.username || "Your account", menu: [{ label: t`Account & two-step sign-in`, href: "/mfa" }, { label: t`API access & connected apps`, href: "/account/api-access" }],
        onSignOut: () => { void logout("person").catch(() => undefined).finally(() => { forgetOfflineMemberData(); client.clear(); window.location.assign(memberHome); }); } }}>
      {children({ slug: makerspaceSlug, makerspaceId: bootstrap?.makerspace.id, path, ready: !member.loading && Boolean(bootstrap),
        bootstrapError: bootstrapQuery.isError, features: bootstrap?.features ?? [] })}
    </MemberPortalTabs>
  </div>;
}
