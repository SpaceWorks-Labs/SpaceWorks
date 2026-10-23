import { MemberUsagePanel } from "./MemberUsagePanel";
import { MemberSectionNavigation } from "./MemberSectionNavigation";
import { MemberPortalTabs, useMemberTab } from "./MemberPortalTabs";
import { SupportContact } from "../../components/SupportContact";
import { CenteredCardLayout } from "../../components/layouts";
import { EmptyState, StatusPill } from "../../components/ui";
import { MemberScreenLayout } from "./MemberScreenLayout";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import type { ArchivedPaymentSummary, MembershipPolicyEnum } from "../../generated/api";
import { bootstrapTenant, logout, memberRequest, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { MemberAuthPanel } from "./MemberAuthPanel";
import { MyBookings } from "../bookings/MyBookings";
import { InvitationRequestForm } from "./InvitationRequestForm";
import { JoinMembershipCta } from "./JoinMembershipCta";
import { PresencePanel } from "../presence/PresencePanel";
import { usePresenceCurrent } from "../presence/api";
import { MemberCertifications } from "./MemberCertifications";
import { MemberActivityPanel, type MemberActivity } from "./MemberActivity";
import { MemberDues, MemberHistory, MemberNotices, MemberTerm } from "./MemberDashboardSections";
import { PartnerEvents } from "./PartnerEvents";
import { MemberDirectory } from "./MemberDirectory";
import { MakerspaceDiscovery } from "./MakerspaceDiscovery";
import { MemberCardPanel } from "./MemberCardPanel";
import { MemberInstall } from "./MemberInstall";
import { forgetOfflineMemberData } from "./memberCard/offlineCard";
import { MemberProfilePanel } from "./MemberProfilePanel";
import { MemberReferrals, type ClaimableInvitation } from "./MemberReferrals";
import { MemberPaymentRows, type MemberPayment } from "./MemberPayments";
import { MemberVerifierPanel } from "./MemberVerifierPanel";
import { MemberClaimRedemption } from "./MemberClaimRedemption";
import { hasClaimSession, MemberClaimSession } from "./MemberClaimSession";
import { AdmissionJoin } from "./AdmissionJoin";
import { MemberAdmission, MemberVouch } from "./MemberAdmission";
import { admissionKeys, publicAdmission, ownAdmission, type AdmissionRequest } from "./membershipAdmissionApi";
import type { CustomAnswers } from "../forms/customFormTypes";
import { MemberNotifications } from "../notifications/MemberNotifications";
import { MemberEventHistoryLink } from "./MemberEventHistoryLink";
import { MyNotificationSettings } from "../notifications/MyNotificationSettings";
import { usePreferences } from "../notifications/channelsApi";
import { MemberPhoneVerification } from "./MemberPhoneVerification";

type Membership = { makerspace: { slug: string; name: string }; membership_status: string; role: string; waiver_acceptance_required: boolean; can_refer: boolean; can_verify: boolean; verified_at: string | null; referrals_enabled: boolean };
type Memberships = { memberships: Membership[]; requests: (Partial<AdmissionRequest> & { makerspace: { id?: number; slug: string; name: string }; state: string; kind: string })[] };
type Waiver = { has_waiver: boolean; body?: string; version?: string };
type Invitations = { invitations: ClaimableInvitation[] };
type Profile = { email_verified: boolean; username?: string };
type ReferralOutcome = { state: "invited" };
type ClaimOutcome = { id: number; outcome: "active" | "pending_approval" | "awaiting_vouches" | "awaiting_payment" };
function message(error: unknown) {
  if (error instanceof StructuredApiError && error.status === 401) return "Sign in to manage your membership.";
  return error instanceof Error ? error.message : "Unable to complete that action.";
}

export function MemberArea() {
  const { slug = "" } = useParams();
  const client = useQueryClient();
  const [search] = useSearchParams();

  const [restoring, setRestoring] = useState(true);
  const [showSignIn, setShowSignIn] = useState(false);
  const [hasPartnerEvents, setHasPartnerEvents] = useState(false);
  const [claimSession, setClaimSession] = useState(hasClaimSession);
  useEffect(() => {
    refreshAccessToken("member").then(() => { setClaimSession(hasClaimSession()); return client.invalidateQueries({ queryKey: ["member"] }); }).finally(() => setRestoring(false));
  }, [client]);
  const bootstrap = useQuery({ queryKey: ["member", slug, "bootstrap"], queryFn: () => bootstrapTenant({ slug: slug || undefined }), retry: false });
  const brandStyle = useTenantBranding(bootstrap.data);
  const spaceName = bootstrap.data?.branding?.display_name || bootstrap.data?.makerspace.name || "Space Works";
  const spaceLogo = bootstrap.data?.branding?.logo_url || bootstrap.data?.makerspace.logo_url || undefined;
  const resolvedSlug = slug || bootstrap.data?.makerspace.slug || "";
  const makerspaceId = bootstrap.data?.makerspace.id ?? -1;
  const memberships = useQuery({ queryKey: ["member", "memberships"], queryFn: () => memberRequest<Memberships>("/memberships/me"), enabled: !claimSession && !restoring, retry: false });
  const unauthenticated = memberships.error instanceof StructuredApiError && memberships.error.status === 401;
  const membershipRefused = memberships.error instanceof StructuredApiError && [400, 401, 403, 404].includes(memberships.error.status);
  const memberAccess = !claimSession && !memberships.error ? memberships.data : undefined;
  const membership = memberAccess?.memberships.find((row) => row.makerspace.slug === resolvedSlug);
  const requestRecord = memberAccess?.requests.find((row) => row.makerspace.slug === resolvedSlug && ["requested", "awaiting_vouches", "awaiting_payment"].includes(row.state));
  const latestApplication = memberAccess?.requests.filter((row) => row.makerspace.slug === resolvedSlug).sort((left, right) => (right.id ?? 0) - (left.id ?? 0))[0];
  const requested = Boolean(requestRecord);
  // Declared before the queries below, which gate on it. The activity endpoint enforces
  // `require_module(makerspace, "membership")`, so calling it with the module off just
  // errors -- the dashboard simply does not exist for a space that runs no memberships.
  const activeTab = useMemberTab(bootstrap.data?.modules ?? []);
  const membershipModuleOn = (bootstrap.data?.modules ?? []).includes("membership");
  // The server derives ties from owned loans/bookings/events as well as memberships.
  const messagingEnabled = makerspaceId >= 0 && Boolean(memberAccess) && !restoring && !claimSession
    && (!membership || membership.membership_status === "active");
  const messaging = usePreferences(makerspaceId, true, messagingEnabled);
  const messagingAllowed = messagingEnabled && messaging.isSuccess;
  const accountSections = ["profile", "card", "certifications", "community", "invitations", "channels", "phone"].filter(key => key === "channels"
    ? messagingAllowed
    : key === "phone" ? messagingAllowed || membership?.membership_status === "active"
    : key === "certifications"
    ? membership?.membership_status === "active" && Boolean(bootstrap.data?.modules.includes("machines"))
    : key === "invitations" ? Boolean(memberAccess && resolvedSlug && makerspaceId >= 0)
      : membershipModuleOn && membership?.membership_status === "active");
  // Preserve old links and signed OAuth returns while presenting one settings surface.
  const requestedSection = search.has("state") || search.get("section") === "messaging" ? "channels" : search.get("section");
  const section = activeTab === "account" ? requestedSection && accountSections.includes(requestedSection) ? requestedSection : accountSections[0] || "access"
    : requestedSection || (activeTab === "loans" ? "current" : activeTab === "events" ? "going" : activeTab === "inbox" ? "notices" : "");
  const accountSelfService = Boolean(membershipModuleOn && membership?.membership_status === "active" && bootstrap.data?.modules.includes("member_accounts") && (bootstrap.data.features?.includes("membership.self_service") || bootstrap.data.features?.includes("membership.self_export")));

  useEffect(() => {
    if (membershipRefused || (memberships.isSuccess && bootstrap.isSuccess && (!membership || membership.membership_status !== "active" || !membershipModuleOn))) forgetOfflineMemberData();
  }, [membershipRefused, memberships.isSuccess, bootstrap.isSuccess, membership, membershipModuleOn]);
  const canApply = !membership || (membershipModuleOn && membership.membership_status === "revoked");
  const canReadApplication = membership?.membership_status !== "revoked" || requested;
  const admission = useQuery({ queryKey: admissionKeys.public(resolvedSlug), queryFn: () => publicAdmission(resolvedSlug), enabled: Boolean(resolvedSlug) && membershipModuleOn && !claimSession, retry: false });
  const ownApplication = useQuery({ queryKey: admissionKeys.own(makerspaceId), queryFn: () => ownAdmission(makerspaceId), enabled: makerspaceId >= 0 && membershipModuleOn && Boolean(latestApplication?.id) && canReadApplication && !claimSession, retry: false });
  const profile = useQuery({ queryKey: ["member", "profile"], queryFn: () => memberRequest<Profile>("/auth/me"), enabled: !claimSession && Boolean(memberships.data), retry: false });
  const invitations = useQuery({ queryKey: ["member", "invitations"], queryFn: () => memberRequest<Invitations>("/memberships/invitations"), enabled: !claimSession && Boolean(memberships.data), retry: false });
  const waiver = useQuery({ queryKey: ["member", resolvedSlug, "waiver"], queryFn: () => memberRequest<Waiver>(`/member/makerspaces/${makerspaceId}/waiver`), enabled: makerspaceId >= 0 && membership?.membership_status === "active", retry: false });
  // Presence also admits account-only guests, so it is gated on the module and a signed-in
  // account, not on membership; a non-active (revoked/suspended) membership is refused.
  const presenceOn = Boolean(resolvedSlug && memberAccess && bootstrap.data?.modules.includes("presence")) && (!membership || membership.membership_status === "active");
  const presence = usePresenceCurrent(resolvedSlug, presenceOn);
  const [presenceSheet, setPresenceSheet] = useState(false);
  const activity = useQuery({ queryKey: ["member", resolvedSlug, "activity"], queryFn: () => memberRequest<MemberActivity>(`/member/makerspaces/${makerspaceId}/activity`), enabled: makerspaceId >= 0 && membership?.membership_status === "active" && membershipModuleOn, retry: false });
  useEffect(() => {
    if (activity.error instanceof StructuredApiError && [400, 401, 403, 404].includes(activity.error.status)) forgetOfflineMemberData();
  }, [activity.error]);
  // Disabled TanStack queries retain cached data. Hide it immediately if the
  // membership gate closes or the server refuses a refreshed activity read.
  const memberActivity = membershipModuleOn && membership?.membership_status === "active" && !activity.error ? activity.data : undefined;
  // NOT gated on an active membership: a loan deposit is raised against a BORROWER, who
  // needs an active account rather than a membership, and the backend now admits a caller
  // to charges in their own name. Gating here would hide a debt from the person who owes it.
  const payments = useQuery({ queryKey: ["member", resolvedSlug, "payments"], queryFn: () => memberRequest<MemberPayment[]>(`/member/makerspaces/${makerspaceId}/payments`), enabled: makerspaceId >= 0 && !claimSession, retry: false });
  const paymentRows = unauthenticated || payments.error ? undefined : payments.data;
  // Deliberately NOT gated on `memberships.data`. A member whose only makerspace is archived
  // gets an empty `/memberships/me`, and a signed-out one gets a 401 -- gating on it meant the
  // people this recovery route exists for were exactly the people who never saw the link.
  const archivedPayments = useQuery({ queryKey: ["member", "archived-payments"], queryFn: () => memberRequest<ArchivedPaymentSummary[]>("/member/archived-payments"), enabled: !claimSession, retry: false });
  // A 404 means the payments app is TOMBSTONED on this deployment, so the recovery route is
  // genuinely gone -- advertising it would hand the member a link straight to a not-found
  // page. Every other error (401 signed-out, network) still warrants the fallback.
  const archivedRemoved = archivedPayments.error instanceof StructuredApiError && archivedPayments.error.status === 404;
  const archivedUnknown = !archivedRemoved && (archivedPayments.isError || (bootstrap.isError && !archivedPayments.data?.length));
  // The layout swaps its body for an error block when this holds, which would also swallow the sign-in controls.
  const bootstrapBlocked = bootstrap.isError && !archivedUnknown && !archivedPayments.data?.length;
  const refresh = () => client.invalidateQueries({ queryKey: ["member"] });
  const presencePanel = activeTab === "overview" ? <PresencePanel enabled={presenceOn} slug={resolvedSlug} spaceName={spaceName} member={membership?.membership_status === "active"}
    selfCheckIn={Boolean(bootstrap.data?.makerspace.geofence_enabled)} sheetOpen={presenceSheet} onSheetOpenChange={setPresenceSheet} /> : null;
  const request = useMutation({ mutationFn: (applicationAnswers: CustomAnswers) => memberRequest<{ outcome: string; state: string }>(`/public/${resolvedSlug}/membership-requests`, { method: "POST", body: JSON.stringify({ application_answers: applicationAnswers }) }), onSuccess: refresh });
  const accept = useMutation({ mutationFn: () => memberRequest(`/member/makerspaces/${makerspaceId}/waiver/accept`, { method: "POST" }), onSuccess: refresh });
  const refer = useMutation({ mutationFn: (inviteEmail: string) => memberRequest<ReferralOutcome>(`/member/makerspaces/${makerspaceId}/referrals`, { method: "POST", body: JSON.stringify({ invite_email: inviteEmail }) }), onSuccess: refresh });
  const claim = useMutation({ mutationFn: ({ id, answers }: { id: number; answers: CustomAnswers }) => memberRequest<ClaimOutcome>(`/memberships/invitations/${id}/claim`, { method: "POST", body: JSON.stringify({ application_answers: answers }) }), onSuccess: refresh });
  const generatePaymentLink = useMutation({ mutationFn: (id: number) => memberRequest<{ checkout_url: string }>(`/member/makerspaces/${makerspaceId}/payments/${id}/checkout`, { method: "POST" }), onSuccess: (data) => { refresh(); window.location.assign(data.checkout_url); } });
  const spaceInvitations = invitations.data?.invitations.filter((item) => item.makerspace.slug === resolvedSlug && (membershipModuleOn || item.is_staff)) ?? [];
  const error = bootstrap.error ?? (!unauthenticated ? memberships.error : null) ?? request.error ?? accept.error ?? activity.error ?? generatePaymentLink.error;
  const policy: MembershipPolicyEnum | undefined = bootstrap.data?.makerspace.membership_policy;
  // The card panel exists only where the `membership` module is installed -- the card is
  // hung off a membership, so every one of its endpoints refuses with 400 without it.

  if (restoring) return <CenteredCardLayout title="Your makerspace access" body="Restoring session..." primary={{ label: "Browse catalogue", href: slug ? `/m/${slug}` : "/" }} state={{ status: "loading" }} />;
  if (claimSession && bootstrap.data) return <div style={brandStyle}><MemberClaimSession slug={resolvedSlug} makerspaceId={makerspaceId} modules={bootstrap.data.modules} geofenceEnabled={bootstrap.data.makerspace.geofence_enabled} name={spaceName} logoUrl={spaceLogo} /></div>;
  if (showSignIn) return <div style={brandStyle}><MemberAuthPanel tenantBrand={bootstrap.data ? { name: spaceName, logo: spaceLogo } : undefined} makerspaceSlug={resolvedSlug} onAuthenticated={() => { setShowSignIn(false); void client.invalidateQueries({ queryKey: ["member"] }); }} /><div className="px-5 pb-5"><SupportContact branding={bootstrap.data?.branding} /></div></div>;

  return <div style={brandStyle}>
    <MemberPortalTabs modules={bootstrap.data?.modules ?? []} active={activeTab}
      workspace={bootstrap.data ? { name: bootstrap.data.makerspace.name, subtitle: membership?.membership_status ?? "Member area",
        avatar: spaceLogo ? { kind: "image", src: spaceLogo } : { kind: "avatar", name: bootstrap.data.makerspace.name, seed: resolvedSlug }, locked: true } : undefined}
      // A signed-out visitor gets a way in, not "Your account" and "Sign out".
      user={unauthenticated ? { name: "Not signed in", menu: [{ label: "Sign in", onClick: () => setShowSignIn(true) }] }
        : { name: profile.data?.username || "Your account", menu: [{ label: "Account & two-step sign-in", href: "/mfa" }, { label: "Delete account", href: `${slug ? `/m/${encodeURIComponent(slug)}` : ""}/member/account?section=deletion` }],
        onSignOut: () => { void logout("member").catch(() => undefined).finally(() => { forgetOfflineMemberData(); client.clear(); window.location.assign(slug ? `/m/${slug}/member` : "/member"); }); } }}>
    <MemberSectionNavigation><MemberScreenLayout tab={activeTab} section={section} hasPartnerEvents={hasPartnerEvents} accountSections={accountSections} accountSelfService={accountSelfService} canRefer={Boolean(membershipModuleOn && membership?.membership_status === "active" && membership.can_refer && membership.referrals_enabled)} member={membership?.membership_status === "active"} status={membership?.membership_status} requested={requested}
      name={bootstrap.data?.makerspace.name || "Space Works"} slug={resolvedSlug} modules={bootstrap.data?.modules ?? []}
      activity={memberActivity} state={bootstrap.isLoading ? { status: "loading" } : bootstrapBlocked ? { status: "error", error: "Couldn't load your makerspace. Try again.", onRetry: () => void bootstrap.refetch() } : { status: "ready" }}
      primary={presenceOn && activeTab === "overview" && presence.isSuccess && !presence.data.active ? { label: "Check in", onClick: () => setPresenceSheet(true) } : undefined}>
    {membershipModuleOn ? <MemberInstall name={bootstrap.data?.branding?.display_name || bootstrap.data?.makerspace.name || "Space Works member"} /> : null}
    {activeTab === "account" && profile.data ? <Link className="desk-button-brand inline-flex" to="/mfa">Manage two-step sign-in</Link> : null}
    {archivedPayments.data?.length ? <section className="desk-panel p-5"><h2 className="title-panel">Payments from closed makerspaces</h2><p className="mt-1 text-sm text-muted">Receipts and outstanding charges remain available after a makerspace closes.</p><Link className="desk-button-brand mt-4 inline-flex" to="/member/archived">View archived payments</Link></section> : null}
    {archivedUnknown ? <section className="desk-panel p-5"><h2 className="title-panel">Closed makerspace?</h2><p className="mt-1 text-sm text-muted">If a makerspace you belonged to has closed, its receipts and any outstanding charges are still reachable. You may need to sign in there.</p><Link className="desk-button-brand mt-4 inline-flex" to="/member/archived">View archived payments</Link></section> : null}
    {bootstrap.isLoading ? <section className="desk-panel p-5 text-sm text-muted">Loading makerspace joining options…</section> : null}
    {bootstrap.isError ? <section className="desk-panel p-5"><p className="text-sm text-danger" role="alert">{message(bootstrap.error)}</p></section> : null}
    {activeTab === "overview" && policy && canApply && !requested && memberships.isLoading ? <section className="desk-panel p-5 text-sm text-muted">Checking your sign-in status…</section> : null}
    {activeTab === "overview" && policy && canApply && !requested && !memberships.isLoading ? membershipModuleOn ? admission.data ? <AdmissionJoin key={resolvedSlug} settings={admission.data} signedIn={Boolean(memberships.data)} pending={request.isPending} error={request.error} onJoin={(answers) => request.mutate(answers)} onSignIn={() => setShowSignIn(true)} /> : <section className="desk-panel p-5"><p className={admission.isError ? "text-sm text-danger" : "text-sm text-muted"} role={admission.isError ? "alert" : undefined}>{admission.error?.message ?? "Loading admission conditions…"}</p></section> : <JoinMembershipCta policy={policy} signedIn={Boolean(memberships.data)} pending={request.isPending} onJoin={() => request.mutate({})} onSignIn={() => setShowSignIn(true)} /> : null}
    {activeTab === "overview" && membershipModuleOn && admission.data?.join_mode !== "closed" && admission.isSuccess && resolvedSlug && canApply && !requested && !memberships.isLoading ? <InvitationRequestForm slug={resolvedSlug} /> : null}
    {activeTab === "overview" && (membershipModuleOn && latestApplication?.id ? <MemberAdmission makerspaceId={makerspaceId} request={ownApplication.data?.id === latestApplication.id && ownApplication.data.state === latestApplication.state ? ownApplication.data : latestApplication as AdmissionRequest} /> : requested ? <section className="desk-panel p-5"><h2 className="title-panel">Membership request sent</h2><p className="mt-1 text-sm text-muted">Staff will review your request.</p></section> : null)}
    {activeTab === "overview" && canReadApplication && ownApplication.error ? <p className="text-sm text-danger" role="alert">{ownApplication.error.message}</p> : null}
    {unauthenticated && resolvedSlug ? <MemberClaimRedemption slug={resolvedSlug} onRedeemed={() => setClaimSession(true)} /> : null}
    {!membership ? presencePanel : null}
    {activeTab === "account" && !claimSession ? <nav aria-label="Personal account tools" className="flex flex-wrap gap-3"><Link className="desk-button" to={`${slug ? `/m/${slug}` : ""}/member/account/saved-details`}>Saved details</Link><Link className="desk-button" to={`${slug ? `/m/${slug}` : ""}/member/account/security-activity`}>Security activity</Link></nav> : null}
    {membership ? <>{activeTab === "overview" ? <section className={`desk-panel ${membership.membership_status === "active" ? "border-success" : "border-warn"} p-5`}><h2 className="title-panel">Membership</h2><div className="mt-2 flex flex-wrap items-center gap-3"><StatusPill label={membership.membership_status} tone={membership.membership_status === "active" ? "success" : "warn"} /><p className="text-sm text-muted">{membership.makerspace.name} · {membership.role.replace(/_/g, " ")}</p></div></section> : null}
      {activeTab === "account" && membershipModuleOn && bootstrap.data?.modules.includes("member_accounts") && membership.membership_status === "active" && (bootstrap.data?.features?.includes("membership.self_service") || bootstrap.data?.features?.includes("membership.self_export")) ? <Link className="desk-button-brand inline-flex" to={`${slug ? `/m/${slug}/member` : "/member"}/account`}>Manage your account</Link> : null}
      {activeTab === "overview" && waiver.data?.has_waiver ? <section id="current-waiver" className="desk-panel p-5"><h2 className="title-panel">Current waiver (<span className="tabular-nums">{waiver.data.version}</span>)</h2><p className="mt-3 max-w-prose whitespace-pre-wrap break-words text-sm text-muted">{waiver.data.body}</p>{membership.waiver_acceptance_required ? <button className="desk-button-brand mt-4" disabled={accept.isPending} onClick={() => accept.mutate()}>Accept waiver</button> : <p className="mt-3 text-sm text-success-ink">Current waiver acceptance is on file.</p>}</section> : null}
      {activeTab === "overview" && membershipModuleOn && membership.membership_status === "active" && membership.can_verify ? <MemberVerifierPanel makerspaceId={makerspaceId} /> : null}
      {activeTab === "overview" && membershipModuleOn && membership.membership_status === "active" && admission.data?.join_mode === "vouch" ? <MemberVouch makerspaceId={makerspaceId} /> : null}
      {/* The check-in action lives with its status, so it survives on layouts whose header primary is something else. */}
      {presencePanel}
      {/* Notices first: they are the reason to open a dashboard at all. */}
      {(activeTab === "overview" || activeTab === "inbox" && section === "notices") && memberActivity ? <MemberNotices notices={memberActivity.notices} /> : null}
      {activeTab === "account" && section === "certifications" && membership?.membership_status === "active" && (bootstrap.data?.modules ?? []).includes("machines") ? <MemberCertifications key={makerspaceId} makerspaceId={makerspaceId} /> : null}
      {activeTab === "inbox" && membership.membership_status === "active" && bootstrap.data?.modules.includes("notifications") ? <MemberNotifications makerspaceId={makerspaceId} features={bootstrap.data.features ?? []} /> : null}
      {(["overview", "events", "bookings"].includes(activeTab) && section !== "partners" || activeTab === "loans" && section !== "history") && memberActivity ? <MemberActivityPanel modules={bootstrap.data?.modules ?? []} section={activeTab === "overview" ? "overview" : activeTab as "loans" | "bookings" | "events"} activity={memberActivity} eventPeriod={section === "past" ? "past" : "going"} makerspaceId={makerspaceId} makerspaceSlug={resolvedSlug} makerspaceName={spaceName} /> : null}
      {activeTab === "overview" && memberActivity ? <MemberTerm term={memberActivity.membership_term} /> : null}
      {activeTab === "overview" && membershipModuleOn && membership.membership_status === "active" ? <MemberCardPanel compact cardHref={`${slug ? `/m/${slug}/member` : "/member"}/account-portal?section=card`} makerspaceId={makerspaceId} spaceName={membership.makerspace.name} /> : null}
      {activeTab === "payments" && memberActivity ? <MemberDues dues={memberActivity.membership_dues} /> : null}
      {activeTab === "loans" && section === "history" && memberActivity ? <MemberHistory loans={memberActivity.loan_history} requests={memberActivity.request_history} /> : null}
      {activeTab === "events" && bootstrap.data?.modules.includes("events") && membership?.membership_status === "active" ? <div hidden={section !== "partners"}><PartnerEvents makerspaceId={makerspaceId} slug={resolvedSlug} onAvailable={setHasPartnerEvents} visible={section === "partners"} /></div> : null}
      {activeTab === "account" && membership.membership_status === "active" && makerspaceId >= 0 && membershipModuleOn ? <>{section === "profile" ? <MemberProfilePanel makerspaceId={makerspaceId} /> : section === "card" ? <MemberCardPanel makerspaceId={makerspaceId} spaceName={membership.makerspace.name} /> : section === "community" ? <MemberDirectory makerspaceId={makerspaceId} /> : null}</> : null}</> : null}
    {activeTab === "overview" && memberAccess && makerspaceId >= 0 ? <MemberUsagePanel key={makerspaceId} makerspaceId={makerspaceId} /> : null}
    {activeTab === "account" && section === "channels" && messagingAllowed ? <MyNotificationSettings key={makerspaceId} makerspaceId={makerspaceId} member /> : null}
    {activeTab === "account" && messagingEnabled && messaging.isLoading ? <p role="status">Checking notification access…</p> : null}
    {activeTab === "account" && messagingEnabled && messaging.error ? <div role="alert"><p>{message(messaging.error)}</p><button className="desk-button" onClick={() => void messaging.refetch()}>Retry notification access</button></div> : null}
    {activeTab === "account" && section === "phone" && (messagingAllowed || membership?.membership_status === "active") ? <MemberPhoneVerification /> : null}
    {activeTab === "overview" && memberships.data ? <MakerspaceDiscovery currentSlug={resolvedSlug} memberships={memberships.data.memberships} requests={memberships.data.requests} /> : null}
    {/* OUTSIDE the membership branch. A loan deposit is raised against a borrower, who
        needs an active account rather than a membership -- nesting this meant the person
        who owed the money was the one person who could not see it. */}
    {activeTab === "payments" && paymentRows?.length ? <section className="desk-panel p-5"><h2 className="title-panel">Payments</h2><MemberPaymentRows makerspaceId={makerspaceId} refunds payments={paymentRows} checkoutPaymentId={generatePaymentLink.isPending ? generatePaymentLink.variables : undefined} onCheckout={(paymentId) => generatePaymentLink.mutate(paymentId)} /></section> : null}
    {activeTab === "account" && section === "invitations" && memberAccess && resolvedSlug && makerspaceId >= 0 ? <MemberReferrals
      canRefer={membershipModuleOn && membership?.membership_status === "active" && membership.can_refer}
      referralsEnabled={membershipModuleOn && membership?.membership_status === "active" && membership.referrals_enabled}
      emailVerified={profile.data?.email_verified}
      invitations={spaceInvitations}
      invitationsLoading={invitations.isLoading}
      invitationError={invitations.error instanceof Error ? invitations.error : null}
      onRefer={(email) => refer.mutateAsync(email)}
      applicationSchema={membershipModuleOn ? admission.data?.application_schema : null}
      admissionMode={membershipModuleOn ? admission.data?.join_mode : undefined}
      onClaim={(id, answers) => claim.mutate({ id, answers: answers ?? {} })}
      isReferring={refer.isPending}
      claimingId={claim.isPending ? claim.variables.id : null}
      referralError={refer.error instanceof Error ? refer.error : null}
      referralSuccess={refer.data ? "Referral invitation sent." : null}
      claimError={claim.error instanceof Error ? claim.error : null}
      claimSuccess={claim.data ? claim.data.outcome === "active" ? "You are now an active member." : claim.data.outcome === "awaiting_payment" ? "Your invitation is awaiting payment before activation." : claim.data.outcome === "awaiting_vouches" ? "Your invitation is awaiting member vouches." : "Your invitation is waiting for manager approval." : null}
    /> : null}
    {unauthenticated && !showSignIn && policy?.startsWith("invite") ? <p className="text-sm text-muted">Sign in to view memberships or claim an invitation.</p> : null}
    {error ? <p className="text-sm text-danger" role="alert">{message(error)}</p> : null}
    {memberships.isError && !unauthenticated ? <Link className="desk-button-brand inline-flex" to="/admin">Sign in</Link> : null}
    {activeTab === "bookings" && !unauthenticated && memberships.isSuccess && bootstrap.data?.modules.includes("bookings") ? <MyBookings slug={resolvedSlug} /> : null}
    {/* Event history needs only an account: an attendee without a membership reaches it from Home. */}
    {!unauthenticated && memberships.isSuccess && bootstrap.data?.modules.includes("events") && (activeTab === "events" || activeTab === "overview" && membership?.membership_status !== "active") ? <MemberEventHistoryLink slug={slug} /> : null}
    {unauthenticated ? <button type="button" className="desk-button-brand" onClick={() => setShowSignIn(true)}>Sign in to your account</button> : null}
    {["loans", "events", "inbox"].includes(activeTab) && !memberships.isLoading && membership?.membership_status !== "active" ? <p className="text-sm text-muted">An active membership is required to view your activity.</p> : null}
    {activeTab === "inbox" && section === "notices" && memberActivity && !memberActivity.notices?.length ? <EmptyState message="No notices need your attention." /> : null}
    {["loans", "bookings", "events", "inbox"].includes(activeTab) && activity.isLoading ? <p role="status" className="text-sm text-muted">Loading your activity...</p> : null}
    {activeTab === "payments" && payments.isLoading ? <p role="status" className="text-sm text-muted">Loading payments...</p> : null}
    {activeTab === "payments" && !unauthenticated && payments.isSuccess && !paymentRows?.length ? <EmptyState message="Nothing to pay. You are all settled." /> : null}
    {activeTab === "payments" && payments.error ? <p role="alert" className="text-sm text-danger">{message(payments.error)}</p> : null}
    <SupportContact branding={bootstrap.data?.branding} />
    </MemberScreenLayout>
    {/* A failed bootstrap must not strand a signed-out visitor: sign-in and invitation-code claim stay reachable. */}
    {bootstrapBlocked ? <div className="mt-5 grid gap-5">
      {unauthenticated && slug ? <MemberClaimRedemption slug={slug} onRedeemed={() => setClaimSession(true)} /> : null}
      {unauthenticated ? <button type="button" className="desk-button-brand" onClick={() => setShowSignIn(true)}>Sign in to your account</button> : null}
      {memberships.isError && !unauthenticated ? <Link className="desk-button-brand inline-flex" to="/admin">Sign in</Link> : null}
    </div> : null}
    </MemberSectionNavigation>
    </MemberPortalTabs>
  </div>;
}
