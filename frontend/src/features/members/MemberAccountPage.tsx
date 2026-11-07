import { MemberHistoryLinks } from "./MemberHistoryLinks";
import { t } from "@lingui/core/macro";
import { forgetOfflineMemberData } from "./memberCard/offlineCard";
import { MemberSectionNavigation } from "./MemberSectionNavigation";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import { CenteredCardLayout, SettingsLayout } from "../../components/layouts";
import { MemberPortalTabs } from "./MemberPortalTabs";
import { bootstrapTenant, refreshAccessToken, logout } from "../../lib/api";
import { hasClaimSession } from "./MemberClaimSession";
import { MemberAuthPanel } from "./MemberAuthPanel";
import { OrganizationSelfCreation, useOrganizationSelfCreationVisible } from "../organizations/OrganizationSelfCreation";
import { MemberAccountProfile } from "./MemberAccountProfile";
import { MemberAccountSessions } from "./MemberAccountSessions";
import { MemberAccountMembership } from "./MemberAccountMembership";
import { MemberHistory, MemberPrivacy } from "./MemberAccountLifecycle";
import { OwnOrganizations } from "../organizationLeave/OwnOrganizations";
import { MemberAccountExports } from "./MemberAccountExports";
import { MemberAccountDeletion, AccountDeletionReceipt } from "./MemberAccountDeletion";
import type { DeletionResult } from "./accountDeletionApi";
import { SignOutEverywhere } from "../auth/SignOutEverywhere";
import { AccountLinkCard } from "./accountLink/AccountLinkCard";
import { useMergeSuggested } from "./accountLink/accountLinkApi";
import { LanguageSwitcher } from "../../components/shell/LanguageSwitcher";
import { memberRequest } from "../../lib/api/requests";

export function MemberAccountPage() {
  const { slug = "" } = useParams();
  const location = useLocation();
  const [search] = useSearchParams();
  const requestedSection = search.get("section") || "profile";
  const [restoring, setRestoring] = useState(true);
  const [signIn, setSignIn] = useState(false);
  const [left, setLeft] = useState(false);
  const [deleted, setDeleted] = useState<DeletionResult | null>(null);
  const client = useQueryClient();
  useEffect(() => { setLeft(false); }, [slug]);
  useEffect(() => {
    let active = true;
    void (async () => {
      await client.cancelQueries({ queryKey: ["member", "account"] });
      client.removeQueries({ queryKey: ["member", "account"] });
      const token = await refreshAccessToken("person");
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
  const lifecycleOn = (key: string) => Boolean(data?.modules?.includes("membership") && data.features?.includes(`membership.${key}`));
  const historyOn = lifecycleOn("history");
  const privacyOn = lifecycleOn("consent") || lifecycleOn("erasure");
  const home = slug ? `/m/${slug}/member` : "/member";
  const selfCreationVisible = useOrganizationSelfCreationVisible(!restoring && !signIn && !hasClaimSession());
  const mergeSuggested = useMergeSuggested(!restoring && !signIn && !hasClaimSession());
  if (signIn && !restoring) return <MemberAuthPanel tenantBrand={data ? { name: data.branding?.display_name || data.makerspace.name, logo: data.branding?.logo_url || data.makerspace.logo_url || undefined } : undefined} makerspaceSlug={slug} onAuthenticated={() => { void authenticated(); }} />;
  const tabs = [["profile", "Profile"], ["security", "Security"], ["membership", "Membership"], ["history", t`Membership history`], ["privacy", "Privacy"], ["data", "Your data"], ["deletion", "Delete account"]].filter(([key]) => ["security", "deletion"].includes(key) || (key === "history" ? historyOn : key === "privacy" ? privacyOn : key === "data" ? selfExport : selfService)).map(([key, label]) => ({ key, label, href: `${location.pathname}?section=${key}` }));
  // Security stays available without replacing the tenant's default account section.
  const defaultSection = selfService ? "profile" : selfExport ? "data" : "deletion";
  const section = tabs.some(tab => tab.key === requestedSection) ? requestedSection : defaultSection;
  // Organization self-creation is account-wide, so it rides on the default section rather than a gated tab.
  const showSelfCreation = selfCreationVisible && section === defaultSection;
  if (deleted) return <CenteredCardLayout state={{ status: "ready" }} title={t`Your account`} body={t`Deletion request received.`} content={<AccountDeletionReceipt result={deleted} />} primary={{ label: t`Return home`, href: "/" }} />;
  return <MemberPortalTabs modules={data?.modules ?? []} active="account" space={data ? { id: data.makerspace.id, slug } : undefined} user={{ name: "Your account", menu: [{ label: t`Member area`, href: home }], onSignOut: () => { void logout("person").catch(() => undefined).finally(() => { forgetOfflineMemberData(); client.clear(); setSignIn(true); }); } }}
    workspace={data ? { name: data.makerspace.name || "Space Works", subtitle: t`Your account`, avatar: data.branding?.logo_url || data.makerspace.logo_url ? { kind: "image", src: data.branding?.logo_url || data.makerspace.logo_url || "" } : { kind: "avatar", name: data.makerspace.name || "Space Works", seed: slug }, locked: true } : undefined}>
    <MemberSectionNavigation>{!restoring && !hasClaimSession() && data ? <MemberHistoryLinks slug={slug} modules={data.modules} features={data.features} /> : null}<nav aria-label={t`Personal account tools`} className="mb-5 flex flex-wrap gap-3"><a className="desk-button" href={`${home}/account/saved-details`}>{t`Saved details`}</a><a className="desk-button" href={`${home}/account/security-activity`}>{t`Security activity`}</a><a className="desk-button" href="/account/api-access">{t`API access & connected apps`}</a><a className="desk-button" href={`${home}/event-payouts`}>{t`Event reimbursements`}</a>{data?.features?.includes("events.prize_claims") ? <a className="desk-button" href={`${home}/prizes`}>{t`My prizes`}</a> : null}</nav><SettingsLayout header={{ title: t`Account`, subtitle: t`Your personal profile and sign-in security.`, secondary: { label: t`Profile & card →`, href: `${home}/account-portal` } }}
      state={restoring || (bootstrap.isLoading && !["security", "deletion"].includes(section)) ? { status: "loading" } : bootstrap.error && !["security", "deletion"].includes(section) ? { status: "error", error: t`Couldn't load your account. Try again.`, onRetry: () => void bootstrap.refetch() } : { status: "ready" }}
      tabs={tabs} activeTab={section} sections={[{ id: section, title: tabs.find(tab => tab.key === section)?.label || t`Account access`, rows: <>
        {left ? <p role="status">{t`You have left this makerspace. Your account remains available.`}</p> : null}
        {mergeSuggested && section === defaultSection ? <AccountLinkCard suggested /> : null}
        {!restoring && hasClaimSession() ? <p>{t`Sign in with a full account to manage profile, sessions or exports.`}</p> : null}
        {!restoring && !hasClaimSession() && section === "deletion" ? <MemberAccountDeletion slug={slug} onDeleted={setDeleted} /> : null}
        {!restoring && !hasClaimSession() && section === "security" ? <div className="grid gap-6">
          <a className="desk-button" href="/mfa">{t`Manage two-step sign-in`}</a>
          <AccountLinkCard suggested={mergeSuggested} />
          <SignOutEverywhere signInHref={location.pathname} onSignedOut={() => setSignIn(true)} />
          {selfService && data ? <MemberAccountSessions key={`sessions-${data.makerspace.id}`} makerspaceId={data.makerspace.id} onSignedOut={() => setSignIn(true)} /> : null}
        </div> : null}
        {!restoring && data && !hasClaimSession() && !left ? <>
          {!selfService && !selfExport && !["security", "deletion", "history", "privacy"].includes(section) ? <p>{t`Account self-service is disabled for this makerspace.`}</p> : null}
          {selfService && section === "profile" ? <MemberAccountProfile key={`profile-${data.makerspace.id}`} makerspaceId={data.makerspace.id} /> : null}
          {selfService && section === "membership" ? <MemberAccountMembership key={`membership-${data.makerspace.id}`} makerspaceId={data.makerspace.id} onLeft={() => setLeft(true)} /> : null}
          {historyOn && section === "history" ? <MemberHistory key={`history-${data.makerspace.id}`} makerspaceId={data.makerspace.id} /> : null}
          {privacyOn && section === "privacy" ? <MemberPrivacy key={`privacy-${data.makerspace.id}`} makerspaceId={data.makerspace.id} consentOn={lifecycleOn("consent")} erasureOn={lifecycleOn("erasure")} /> : null}
          {selfExport && section === "data" ? <MemberAccountExports key={`exports-${data.makerspace.id}`} makerspaceId={data.makerspace.id} /> : null}
        </> : null}
      </> }, ...(!restoring && !signIn && !hasClaimSession() && section === (tabs[0]?.key || "profile") ? [{ id: "your-organizations", title: t`Organization memberships`, rows: <OwnOrganizations /> }] : []), ...(showSelfCreation ? [{ id: "create-organization", title: t`Create your organization`, rows: <OrganizationSelfCreation /> }] : []), ...(!restoring && !signIn && !hasClaimSession() && section === defaultSection ? [{ id: "language", title: t`Language`, rows: <LanguageSwitcher variant="select" onPersist={(code) => memberRequest("/auth/me", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preferred_locale: code }) })} /> }] : [])]} /></MemberSectionNavigation>
  </MemberPortalTabs>;
}
