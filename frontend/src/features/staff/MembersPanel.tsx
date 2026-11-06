import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field } from "../../components/ui";
import { PresenceRoster } from "../presence/PresenceRoster";
import { DEFAULT_PRESETS, presenceApi, presenceKeys } from "../presence/api";
import type {
  AdminMembership,
  MembershipListResponse,
  PatchedMembershipCapabilities,
} from "../../generated/api";
import { StructuredApiError, staffRequest } from "../../lib/api";
import { InvitationRequestsSection } from "./InvitationRequestsSection";
import { MembershipPlansSection } from "./MembershipPlansSection";
import { MemberTermsDialog } from "./MemberTermsDialog";
import { useUrlListState } from "../../lib/useUrlListState";
import { ListViewControls } from "./ListViewControls";
import { Panel } from "./panels/shared";
import { MembershipReasonDialog } from "./MembershipReasonDialog";
import { MembershipPagination } from "./MembershipPagination";
import { MembershipPlanPicker } from "./MembershipPlanPicker";
import { MembershipWaiverPanel } from "./MembershipWaiverPanel";
import { MembershipAdmissionReview, type ReviewMembershipRequest } from "./MembershipAdmissionReview";
import { FlowLayout } from "../../components/layouts/FlowLayout";
import { ListLayout } from "../../components/layouts/ListLayout";
import { MemberRow } from "./MemberRow";
import { MembershipLifecycleTab, lifecycleTabs } from "./membershipLifecycle/MembershipLifecycleTabs";
import { BulkDecideBar } from "./membershipLifecycle/BulkDecideBar";
import { FinancialYearSetting } from "./membershipLifecycle/FinancialYearSetting";
import { assignableRoles, type MembershipRoles } from "./panels/roleSets";
import type { StaffRole } from "./panels/rolesApi";

type RosterMember = AdminMembership & MembershipRoles;
type RosterResponse = Omit<MembershipListResponse, "results"> & { results: RosterMember[] };

export const membershipErrorText = (error: unknown) =>
  error instanceof StructuredApiError ? error.detail ?? error.message : t`Unable to update membership.`;

// `membership` gates the COMMUNITY side only. The staff roster, role assignment and
// revoke are core RBAC state and are never gated -- gating them would let a makerspace
// lock itself out of its own administration (plan A7). So the module hides exactly the
// surfaces the backend refuses: the request queue and verification/referral capabilities.
// Waiver management and witnessed acceptance are core liability controls. Invitation stays,
// because a STAFF invitation keeps working with
// the module off (`invite_membership` discriminates on the role's granted actions).
export function MembersPanel({ makerspaceId, membershipEnabled, presenceEnabled = false, canManageMakerspace = true, canViewFinance = false, canRecordPayment = false, actorActions, isSuperadmin, onAuthRefresh, enabledFeatures = [], makerspaceSlug = "" }: { makerspaceId: number; membershipEnabled: boolean; presenceEnabled?: boolean; canManageMakerspace?: boolean; canViewFinance?: boolean; canRecordPayment?: boolean; actorActions: string[]; isSuperadmin: boolean; onAuthRefresh: () => void; enabledFeatures?: string[]; makerspaceSlug?: string }) {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const requestedSection = params.get("section") ?? "members";
  const lifecycle = lifecycleTabs(enabledFeatures, membershipEnabled);
  const availableSections = ["members", "requests", ...(presenceEnabled ? ["presence"] : []), ...(membershipEnabled && canManageMakerspace ? ["plans"] : []), ...(canManageMakerspace ? ["waivers"] : []), ...lifecycle.map((item) => item.key)];
  const tab = availableSections.includes(requestedSection) ? requestedSection : "members";
  const setTab = (section: string) => { const next = new URLSearchParams(params); next.set("section", section); setParams(next, { replace: true }); };
  const [inviteOpen, setInviteOpen] = useState(false);
  const key = ["members", makerspaceId];
  const list = useUrlListState({ id: "", q: "", status: "", ordering: "user__username", page: "1", requestPage: "1", requestState: "", requestOrdering: "-created_at" });
  const rosterPage = list.page;
  const setRosterPage = list.setPage;
  const requestPage = Number(list.values.requestPage);
  const setRequestPage = (page: number) => list.setPage(page, "requestPage");
  const [planId, setPlanId] = useState<number | null>(null);
  const [decision, setDecision] = useState<{ id: number; kind: "member" | "request"; title: string } | null>(null);
  const roster = useQuery({
    queryKey: [...key, "roster", list.query],
    queryFn: () => staffRequest<RosterResponse>(`/admin/memberships?makerspace_id=${makerspaceId}&page=${rosterPage}&${new URLSearchParams({ q: list.values.q, status: list.values.status, ordering: list.values.ordering, id: list.values.id })}`),
  });
  const requests = useQuery({
    queryKey: [...key, "requests", requestPage, membershipEnabled, list.values.requestState, list.values.requestOrdering],
    // Not gated on the module: with it off the backend still lists STAFF invitations
    // (and only those), which staff must be able to approve or cancel.
    queryFn: () => staffRequest<{ results: ReviewMembershipRequest[]; count: number; next: string | null; previous: string | null }>(`/admin/membership-requests?makerspace_id=${makerspaceId}&page=${requestPage}&${new URLSearchParams({ state: list.values.requestState, ordering: list.values.requestOrdering })}`),
  });
  // Module off: no presence tab, no request. Page 1 is shared with the roster tab's own query.
  const presence = useQuery({ queryKey: presenceKeys.roster(makerspaceId, 1), queryFn: () => presenceApi.roster(makerspaceId, 1), enabled: presenceEnabled });
  const presencePolicy = useQuery({ queryKey: ["makerspace-settings", makerspaceId],
    queryFn: () => staffRequest<{ presence_preset_minutes: number[] }>(`/admin/makerspaces/${makerspaceId}`), enabled: presenceEnabled });
  const configuredPresets = presencePolicy.data?.presence_preset_minutes;
  const roles = useQuery({ queryKey: [...key, "roles"], queryFn: () => staffRequest<StaffRole[]>(`/admin/makerspaces/${makerspaceId}/roles`) });
  const grantableRoles = assignableRoles(roles.data ?? [], actorActions, isSuperadmin);
  const [roleId, setRoleId] = useState<number | null>(null);
  // What the dropdown SHOWS: the first role until staff pick another. Approve and Invite
  // must post this, not `roleId` -- that stays null until a change event, so with one role
  // (or the default left alone) both used to send `role_id: null` and fail.
  const selectedRole = (grantableRoles.some((role) => role.id === roleId) ? roleId : grantableRoles[0]?.id) ?? null;
  const [inviteEmail, setInviteEmail] = useState("");
  const [termsMember, setTermsMember] = useState<AdminMembership | null>(null);
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const decisionSaved = () => { setDecision(null); void refresh(); };
  const revoke = useMutation({ mutationFn: ({ id, reason }: { id: number; reason: string }) => staffRequest(`/admin/memberships/${id}/revoke`, { method: "POST", body: JSON.stringify({ reason }) }), onSuccess: decisionSaved });
  const revokeRequest = useMutation({ mutationFn: ({ id, reason }: { id: number; reason: string }) => staffRequest(`/admin/membership-requests/${id}/revoke`, { method: "POST", body: JSON.stringify({ reason }) }), onSuccess: decisionSaved });
  const approve = useMutation({ mutationFn: (id: number) => staffRequest(`/admin/membership-requests/${id}/approve`, { method: "POST", body: JSON.stringify({ role_id: selectedRole, ...(membershipEnabled && planId ? { plan_id: planId } : {}) }) }), onSuccess: refresh });
  const capabilities = useMutation({
    mutationFn: ({ id, next }: { id: number; next: PatchedMembershipCapabilities }) =>
      staffRequest<AdminMembership>(`/admin/memberships/${id}/capabilities`, {
        method: "PATCH",
        body: JSON.stringify(next),
      }),
    onSuccess: refresh,
  });
  const verify = useMutation({
    mutationFn: ({ id, verified }: { id: number; verified: boolean }) =>
      staffRequest<AdminMembership>(`/admin/memberships/${id}/${verified ? "verify" : "unverify"}`, {
        method: "POST",
      }),
    onSuccess: refresh,
  });
  const invite = useMutation({ mutationFn: () => staffRequest(`/admin/makerspace/${makerspaceId}/membership-invitations`, { method: "POST", body: JSON.stringify({ invite_email: inviteEmail, role_id: selectedRole }) }), onSuccess: () => { setInviteEmail(""); refresh(); } });
  const witnessWaiver = useMutation({ mutationFn: (id: number) => staffRequest(`/admin/memberships/${id}/waiver/witness`, { method: "POST", body: JSON.stringify({}) }), onSuccess: refresh });
  const error = revoke.error ?? revokeRequest.error ?? approve.error ?? capabilities.error ?? verify.error ?? invite.error ?? witnessWaiver.error;
  const rosterRows = roster.data?.results ?? [];
  const requestRows = requests.data?.results ?? [];
  const activeQuery = tab === "requests" ? requests : roster;
  // The presence tab owns its loading/error states inside PresenceRoster.
  const querySection = ["members", "requests"].includes(tab);

  const sectionTabs = [
      { key: "members", label: t`Members`, href: "#members", count: roster.data?.count ?? 0 },
      { key: "requests", label: membershipEnabled ? t`Requests` : t`Invitations`, href: "#requests", count: requests.data?.count ?? 0 },
      ...(presenceEnabled ? [{ key: "presence", label: t`Present now`, href: "#presence", count: presence.data?.count ?? 0 }] : []),
      ...(membershipEnabled && canManageMakerspace ? [{ key: "plans", label: t`Plans`, href: "#plans" }] : []),
      ...(canManageMakerspace ? [{ key: "waivers", label: t`Waivers`, href: "#waivers" }] : []),
      ...lifecycle,
    ];
  return <ListLayout state={{ status: querySection && activeQuery.isLoading ? "loading" : querySection && activeQuery.isError ? "error" : "ready", error: t`Couldn't load ${tab === "requests" ? "requests" : "members"}. Try again.`, onRetry: () => { void activeQuery.refetch(); } }}
    tabs={sectionTabs} activeTab={tab} onTabChange={setTab}
    header={{ title: t`Members`, subtitle: t`Membership, permissions and the people making things here.`, primary: { label: t`Invite member`, onClick: () => setInviteOpen(true) } }}
    stats={[{ label: t`Members`, value: roster.data?.count ?? 0 }, { label: membershipEnabled ? t`Membership requests` : t`Invitations`, value: requests.data?.count ?? 0 }, ...(presenceEnabled ? [{ label: t`Currently present`, value: presence.data?.count ?? 0 }] : [])]}
    empty={{ message: t`No members yet. Invite someone to your space.` }}
    body={{ kind: "rows", rows: <>
    {tab === "members" ? <section aria-label={t`Member roster`} className="grid gap-3">
      <ListViewControls state={list} makerspaceId={makerspaceId} entity="members" searchLabel="Search members" sorts={[["user__username", "Username"], ["-user__username", "Username descending"], ["status", "Status"]]} activeCount={Number(Boolean(list.values.status))} controls={<label className="grid gap-1 text-sm">{t`Status`}<select className="desk-input max-w-full" value={list.values.status} onChange={(event) => list.setFilter("status", event.target.value)}><option value="">{t`All`}</option><option value="active">{t`Active`}</option><option value="revoked">{t`Revoked`}</option></select></label>} />
      <p className="mb-4 text-sm text-muted">{t`Membership, referral and verification delegation, waiver compliance, and active presence for this makerspace.`}</p>
      {rosterRows.map((row) => <MemberRow
        key={row.id}
        makerspaceId={makerspaceId}
        member={row}
        roles={grantableRoles}
        onAuthRefresh={onAuthRefresh}
        canManageMakerspace={canManageMakerspace}
        canViewFinance={canViewFinance}
        canRecordPayment={canRecordPayment}
        error={(() => { const failed = capabilities.error ?? verify.error; return failed ? membershipErrorText(failed) : undefined; })()}
        changingCapabilities={capabilities.isPending}
        changingVerification={verify.isPending}
        changingWitness={witnessWaiver.isPending}
        membershipEnabled={membershipEnabled}
        onCapability={(next) => capabilities.mutate({ id: row.id, next })}
        onVerify={() => verify.mutate({ id: row.id, verified: !row.verified_at })}
        onWitness={() => witnessWaiver.mutate(row.id)}
        onRevoke={() => { revoke.reset(); setDecision({ id: row.id, kind: "member", title: t`Revoke ${row.user.display_name || row.user.username}` }); }}
        onTerms={() => setTermsMember(row)}
      />)}
      {roster.isSuccess && !rosterRows.length ? <EmptyState message={t`No members on this page. Invite someone or try another filter.`} /> : null}
      <MembershipPagination label="members" page={rosterPage} next={roster.data?.next} previous={roster.data?.previous} fetching={roster.isFetching} onPage={setRosterPage} />
    </section> : null}
    {tab === "requests" ? <Panel title={membershipEnabled ? t`Membership requests` : t`Invitations`}>
      <div className="mb-3 flex flex-wrap gap-3">
        <label className="text-xs text-muted">{t`Request state`}<select className="desk-input max-w-full" value={list.values.requestState} onChange={(event) => list.update({ requestState: event.target.value, requestPage: "1" }, false)}><option value="">{t`All`}</option>{["requested", "invited", "awaiting_vouches", "awaiting_payment", "expired", "canceled", "active", "revoked"].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="text-xs text-muted">{t`Request sort`}<select className="desk-input max-w-full" value={list.values.requestOrdering} onChange={(event) => list.update({ requestOrdering: event.target.value, requestPage: "1" }, false)}><option value="-created_at">{t`Newest`}</option><option value="created_at">{t`Oldest`}</option><option value="state">{t`State`}</option></select></label>
      </div>
      <Field label={t`Approve as`}><select className="desk-input max-w-full" value={selectedRole ?? ""} onChange={event => setRoleId(Number(event.target.value))}>{grantableRoles.map(role => <option key={role.id} value={role.id}>{role.name}</option>)}</select></Field>
      {roles.isError ? <p role="alert" className="text-sm text-danger">{membershipErrorText(roles.error)}</p> : null}
      {membershipEnabled ? <MembershipPlanPicker makerspaceId={makerspaceId} value={planId} onChange={setPlanId} /> : null}
      {membershipEnabled && enabledFeatures.includes("membership.admission_tools") ? <BulkDecideBar makerspaceId={makerspaceId} rows={requestRows} onDone={refresh} /> : null}
      {requestRows.map((row) => <MembershipAdmissionReview key={row.id} row={row} makerspaceId={makerspaceId}
        manageable={canManageMakerspace || !row.assigned_role || Boolean(roles.data?.some((role) => role.id === row.assigned_role?.id))}
        canViewFinance={canViewFinance} canRecordPayment={canRecordPayment || canManageMakerspace} canWaive={canManageMakerspace}
        approvePending={approve.isPending} declinePending={revokeRequest.isPending} selectedRole={selectedRole}
        onApprove={() => approve.mutate(row.id)} onDecline={() => { revokeRequest.reset(); setDecision({ id: row.id, kind: "request", title: row.state === "invited" ? t`Cancel invitation` : t`Decline membership request` }); }} />)}
      {requests.isLoading ? <p className="text-sm text-muted">{t`Loading requests…`}</p> : null}
      {requests.isError ? <p role="alert" className="text-sm text-danger">{membershipErrorText(requests.error)}</p> : null}
      {requests.isSuccess && !requestRows.length ? <p className="text-sm text-muted">{t`No membership requests on this page.`}</p> : null}
      <MembershipPagination label="requests" page={requestPage} next={requests.data?.next} previous={requests.data?.previous} fetching={requests.isFetching} onPage={setRequestPage} /></Panel> : null}
    {membershipEnabled && tab === "requests" ? <InvitationRequestsSection makerspaceId={makerspaceId} roles={grantableRoles} /> : null}
    {membershipEnabled && canManageMakerspace && tab === "plans" ? <><FinancialYearSetting makerspaceId={makerspaceId} canEdit={canManageMakerspace} /><MembershipPlansSection makerspaceId={makerspaceId} features={enabledFeatures} /></> : null}
    {presenceEnabled && tab === "presence" ? presencePolicy.isSuccess
      ? <PresenceRoster makerspaceId={makerspaceId} presets={configuredPresets?.length ? configuredPresets : DEFAULT_PRESETS} />
      : presencePolicy.isError ? <p role="alert">{t`Couldn't load check-in durations. `}<button type="button" onClick={() => { void presencePolicy.refetch(); }}>{t`Try again`}</button></p>
      : <p role="status">{t`Loading check-in durations…`}</p> : null}
    {canManageMakerspace && tab === "waivers" ? <MembershipWaiverPanel makerspaceId={makerspaceId} /> : null}
    {lifecycle.some((item) => item.key === tab) ? <MembershipLifecycleTab tab={tab} makerspaceId={makerspaceId} slug={makerspaceSlug} features={enabledFeatures} canManageMakerspace={canManageMakerspace} standing={params.get("standing") ?? ""} /> : null}
    {error ? <p className="text-sm text-danger" role="alert">{membershipErrorText(error)}</p> : null}
  </> }} detail={<>
    <FlowLayout presentation="dialog" open={inviteOpen} title={t`Invite member`} state={{ status: "ready" }} steps={[{ key: "invite", label: t`Invitation`, state: "current" }]} current="invite" onCancel={() => setInviteOpen(false)}
      footer={{ next: { label: t`Invite`, pending: invite.isPending, disabled: !inviteEmail || !selectedRole, disabledReason: "Enter an email and choose a role.", onClick: () => invite.mutate(undefined, { onSuccess: () => setInviteOpen(false) }) } }}
      work={<div className="grid gap-4"><Field label={t`Invite role`}><select className="desk-input max-w-full" value={selectedRole ?? ""} onChange={event => setRoleId(Number(event.target.value))}>{grantableRoles.map(role => <option key={role.id} value={role.id}>{role.name}</option>)}</select></Field><Field label={t`Invite email`}><input className="desk-input" type="email" value={inviteEmail} onChange={event => setInviteEmail(event.target.value)} /></Field>{invite.error ? <p role="alert" className="text-danger">{membershipErrorText(invite.error)}</p> : null}</div>} />
    {decision ? <MembershipReasonDialog key={`${decision.kind}-${decision.id}`} title={decision.title} pending={revoke.isPending || revokeRequest.isPending} error={(decision.kind === "member" ? revoke.error : revokeRequest.error) ? membershipErrorText(decision.kind === "member" ? revoke.error : revokeRequest.error) : null} onClose={() => setDecision(null)} onConfirm={(reason) => (decision.kind === "member" ? revoke : revokeRequest).mutate({ id: decision.id, reason })} /> : null}
    {termsMember ? <MemberTermsDialog key={termsMember.id} makerspaceId={makerspaceId} features={enabledFeatures} membershipId={termsMember.id} memberName={termsMember.user.display_name || termsMember.user.username} onClose={() => setTermsMember(null)} /> : null}
  </>} />;
}
