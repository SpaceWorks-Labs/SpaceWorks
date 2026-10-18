import { forgetOfflineMemberData } from "./memberCard/offlineCard";
import { MemberSectionNavigation } from "./MemberSectionNavigation";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import { SettingsLayout } from "../../components/layouts";
import { MemberPortalTabs } from "./MemberPortalTabs";
import { bootstrapTenant, refreshAccessToken, logout } from "../../lib/api";
import { hasClaimSession } from "./MemberClaimSession";
import { MemberAuthPanel } from "./MemberAuthPanel";
import { OrganizationSelfCreation, useOrganizationSelfCreationVisible } from "../organizations/OrganizationSelfCreation";
import { MemberAccountProfile } from "./MemberAccountProfile";
import { MemberAccountSessions } from "./MemberAccountSessions";
import { MemberAccountMembership } from "./MemberAccountMembership";
import { MemberAccountExports } from "./MemberAccountExports";

export function MemberAccountPage() {
  const { slug = "" } = useParams();
  const location = useLocation();
  const [search] = useSearchParams();
  const requestedSection = search.get("section") || "profile";
  const [restoring, setRestoring] = useState(true);
  const [signIn, setSignIn] = useState(false);
  const [left, setLeft] = useState(false);
  const client = useQueryClient();
  useEffect(() => { setLeft(false); }, [slug]);
  useEffect(() => {
    let active = true;
    void (async () => {
      await client.cancelQueries({ queryKey: ["member", "account"] });
      client.removeQueries({ queryKey: ["member", "account"] });
      const token = await refreshAccessToken();
      if (active) { setSignIn(!token); setRestoring(false); }
    })().catch(() => { if (active) { setSignIn(true); setRestoring(false); } });
    return () => { active = false; };
  }, [client]);
  const authenticated = async () => {
    await client.cancelQueries({ queryKey: ["member"] });
    client.removeQueries({ queryKey: ["member"] });
    setLeft(false);
    setSignIn(false);
  };
  const bootstrap = useQuery({ queryKey: ["member", slug, "bootstrap"], queryFn: () => bootstrapTenant({ slug: slug || undefined }), retry: false });
  const data = bootstrap.data;
  const selfService = data?.modules?.includes("membership") && data.modules?.includes("member_accounts") && data.features?.includes("membership.self_service");
  const selfExport = data?.modules?.includes("membership") && data.modules?.includes("member_accounts") && data.features?.includes("membership.self_export");
  const home = slug ? `/m/${slug}/member` : "/member";
  const selfCreationVisible = useOrganizationSelfCreationVisible(!restoring && !signIn && !hasClaimSession());
  if (signIn && !restoring) return <MemberAuthPanel tenantBrand={data ? { name: data.branding?.display_name || data.makerspace.name, logo: data.branding?.logo_url || data.makerspace.logo_url || undefined } : undefined} makerspaceSlug={slug} onAuthenticated={() => { void authenticated(); }} />;
  const tabs = [["profile", "Profile"], ["security", "Security"], ["membership", "Membership"], ["data", "Your data"]].filter(([key]) => key === "data" ? selfExport : selfService).map(([key, label]) => ({ key, label, href: `${location.pathname}?section=${key}` }));
  const section = tabs.some(tab => tab.key === requestedSection) ? requestedSection : tabs[0]?.key || "profile";
  // Organization self-creation is account-wide, so it rides on the first section rather than a gated tab.
  const showSelfCreation = selfCreationVisible && section === (tabs[0]?.key || "profile");
  return <MemberPortalTabs modules={data?.modules ?? []} active="account" user={{ name: "Your account", menu: [{ label: "Member area", href: home }], onSignOut: () => { void logout().catch(() => undefined).finally(() => { forgetOfflineMemberData(); client.clear(); setSignIn(true); }); } }}
    workspace={data ? { name: data.makerspace.name || "Space Works", subtitle: "Your account", avatar: data.branding?.logo_url || data.makerspace.logo_url ? { kind: "image", src: data.branding?.logo_url || data.makerspace.logo_url || "" } : { kind: "avatar", name: data.makerspace.name || "Space Works", seed: slug }, locked: true } : undefined}>
    <MemberSectionNavigation><nav aria-label="Personal account tools" className="mb-5 flex flex-wrap gap-3"><a className="desk-button" href={`${home}/account/saved-details`}>Saved details</a><a className="desk-button" href={`${home}/account/security-activity`}>Security activity</a></nav><SettingsLayout header={{ title: "Account", subtitle: "Your personal profile and sign-in security.", secondary: { label: "Profile & card →", href: `${home}/account-portal` } }}
      state={restoring || bootstrap.isLoading ? { status: "loading" } : bootstrap.error ? { status: "error", error: "Couldn't load your account. Try again.", onRetry: () => void bootstrap.refetch() } : { status: "ready" }}
      tabs={tabs} activeTab={section} sections={[{ id: section, title: tabs.find(tab => tab.key === section)?.label || "Account access", rows: <>
        {left ? <p role="status">You have left this makerspace. Your account remains available.</p> : null}
        {!restoring && hasClaimSession() ? <p>Sign in with a full account to manage profile, sessions or exports.</p> : null}
        {!restoring && data && !hasClaimSession() && !left ? <>
          {!selfService && !selfExport ? <p>Account self-service is disabled for this makerspace.</p> : null}
          {selfService && section === "profile" ? <MemberAccountProfile key={`profile-${data.makerspace.id}`} makerspaceId={data.makerspace.id} /> : null}
          {selfService && section === "security" ? <div className="grid gap-6"><a className="desk-button" href="/mfa">Manage two-step sign-in</a><MemberAccountSessions key={`sessions-${data.makerspace.id}`} makerspaceId={data.makerspace.id} onSignedOut={() => setSignIn(true)} /></div> : null}
          {selfService && section === "membership" ? <MemberAccountMembership key={`membership-${data.makerspace.id}`} makerspaceId={data.makerspace.id} onLeft={() => setLeft(true)} /> : null}
          {selfExport && section === "data" ? <MemberAccountExports key={`exports-${data.makerspace.id}`} makerspaceId={data.makerspace.id} /> : null}
        </> : null}
      </> }, ...(showSelfCreation ? [{ id: "create-organization", title: "Create your organization", rows: <OrganizationSelfCreation /> }] : [])]} /></MemberSectionNavigation>
  </MemberPortalTabs>;
}
