import { t } from "@lingui/core/macro";
import { useState } from "react";
import { DetailLayout } from "../../components/layouts/DetailLayout";
import { ListRow, OverflowMenu, SettingsRow, StatusPill } from "../../components/ui";
import type { AdminMembership, PatchedMembershipCapabilities } from "../../generated/api";
import type { AdmissionVouch } from "../members/membershipAdmissionApi";
import { MembershipVouchers } from "./MembershipAdmissionReview";
import { PaymentReconcileActions } from "./PaymentReconcileActions";
import { MemberRolesControl } from "./panels/MemberRolesControl";
import { MemberEventsSection } from "./MemberEventsSection";
import { MemberMachineAccessSection } from "../machine-access/MemberMachineAccessSection";
import { MemberActivitySection } from "./memberActivity/MemberActivitySection";
import type { MembershipRoles } from "./panels/roleSets";
import type { StaffRole } from "./panels/rolesApi";

export function MemberRow({ makerspaceId, member, roles, onAuthRefresh, canManageMakerspace, canViewFinance, canRecordPayment, membershipEnabled, changingCapabilities, changingVerification, changingWitness, error, onCapability, onVerify, onWitness, onRevoke, onTerms }: {
  makerspaceId: number;
  member: AdminMembership & MembershipRoles;
  /** Roles the actor may grant; the role set is replaced through MemberRolesControl. */
  roles: StaffRole[];
  onAuthRefresh: () => void;
  canManageMakerspace: boolean;
  canViewFinance: boolean;
  canRecordPayment: boolean;
  membershipEnabled: boolean;
  changingCapabilities: boolean;
  changingVerification: boolean;
  changingWitness: boolean;
  /** A failed capability / verification change, shown inside the open drawer instead of behind it. */
  error?: string;
  onCapability: (next: PatchedMembershipCapabilities) => void;
  onVerify: () => void;
  onWitness: () => void;
  onRevoke: () => void;
  onTerms: () => void;
}) {
  const [open, setOpen] = useState(false);
  const active = member.status === "active";
  const manageable = canManageMakerspace || roles.some((role) => role.id === member.assigned_role?.id);
  const displayName = member.user.display_name || member.user.username || "Member";
  const roleNames = member.roles.map((role) => role.name).join(" + ") || "Member";
  return <><ListRow title={displayName} identity={{ kind: "avatar", name: displayName, seed: String(member.user.id) }} onClick={() => setOpen(true)}
    meta={<><span className="[overflow-wrap:anywhere]">{member.user.email || member.user.username}</span> {t` · ${roleNames} · Waiver `}{member.waiver_required ? (member.waiver_current ? "current" : "needed") : t`not required`}</>}
    right={<div className="flex flex-wrap items-center gap-2">
      <StatusPill label={member.status ?? t`Unknown`} tone={active ? "success" : "neutral"} />
      {membershipEnabled ? <StatusPill tone={member.verified_at ? "success" : "neutral"} label={member.verified_at ? t`Verified` : t`Not verified`} /> : null}
      {/* Who owes money is roster-level information: amount, Mark offline and Waive stay on the row. */}
      {canViewFinance && member.payment?.status === "pending" ? <PaymentReconcileActions makerspaceId={makerspaceId} payment={member.payment}
        canRecordPayment={canRecordPayment || canManageMakerspace} canWaive={canManageMakerspace} invalidateKeys={[["members", makerspaceId]]} /> : null}
      {active && member.waiver_required && !member.waiver_current ? <button className="desk-button" disabled={changingWitness} onClick={onWitness}>{t`Record witnessed acceptance`}</button> : null}
      {active ? <OverflowMenu label={t`Actions for ${displayName}`} actions={[
        { label: t`Member details`, onClick: () => setOpen(true) },
        ...(membershipEnabled ? [{ label: member.verified_at ? t`Unverify` : t`Verify`, pending: changingVerification, onClick: onVerify }, { label: t`Terms`, onClick: onTerms }] : []),
        ...(manageable ? [{ label: t`Revoke`, tone: "danger" as const, onClick: onRevoke }] : []),
      ]} /> : null}
    </div>} />
    <DetailLayout presentation="drawer" open={open} onClose={() => setOpen(false)} title={displayName}
      identity={{ kind: "avatar", name: displayName, seed: String(member.user.id) }} status={<StatusPill label={member.status ?? t`Unknown`} tone={active ? "success" : "neutral"} />}
      state={{ status: "ready" }} main={<div className="grid gap-4">
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {/* Only a Space Manager edits the role set; a manage_members actor sees it read-only. */}
        <SettingsRow label={t`Roles`} helper={t`The actions this member can take in this space.`}>{active && manageable && canManageMakerspace
          ? <MemberRolesControl msId={makerspaceId} membershipId={member.id} membership={member} roles={roles} onAuthRefresh={onAuthRefresh} />
          : <span>{roleNames}</span>}</SettingsRow>
        {active && membershipEnabled ? <>
          <SettingsRow label={t`Can refer`} helper={t`Can vouch for a new member.`}><label className="flex min-h-11 items-center gap-3"><input aria-label={t`Can refer`} className="h-5 w-5 accent-accent" type="checkbox" checked={member.can_refer} disabled={changingCapabilities} onChange={event => onCapability({ can_refer: event.target.checked })} />{t`Allow referrals`}</label></SettingsRow>
          <SettingsRow label={t`Can verify`} helper={t`Can verify other members.`}><label className="flex min-h-11 items-center gap-3"><input aria-label={t`Can verify`} className="h-5 w-5 accent-accent" type="checkbox" checked={member.can_verify} disabled={changingCapabilities} onChange={event => onCapability({ can_verify: event.target.checked })} />{t`Allow verification`}</label></SettingsRow>
          <SettingsRow label={t`Verification`}><button className="desk-button" disabled={changingVerification} onClick={onVerify}>{member.verified_at ? t`Unverify` : t`Verify`}</button></SettingsRow>
          <SettingsRow label={t`Membership terms`}><button className="desk-button" onClick={() => { setOpen(false); onTerms(); }}>{t`Terms`}</button></SettingsRow>
        </> : null}
        <SettingsRow label={t`Waiver`}><span>{member.waiver_required ? member.waiver_current ? t`Current` : t`Acceptance needed` : t`Not required`}</span></SettingsRow>
        <MembershipVouchers vouches={(member as AdminMembership & { vouches?: AdmissionVouch[] }).vouches} />
        {canViewFinance && member.payment?.status !== "pending" ? <PaymentReconcileActions makerspaceId={makerspaceId} payment={member.payment} canRecordPayment={canRecordPayment || canManageMakerspace} canWaive={canManageMakerspace} invalidateKeys={[["members", makerspaceId]]} /> : null}
        {/* Mounted only while the drawer is open, so the roster never fetches one history per row. */}
        {open ? <MemberEventsSection makerspaceId={makerspaceId} userId={member.user.id} /> : null}
        {open ? <MemberActivitySection makerspaceId={makerspaceId} userId={member.user.id} /> : null}
        {open && active ? <MemberMachineAccessSection makerspaceId={makerspaceId} userId={member.user.id} name={displayName} /> : null}
      </div>}
      danger={active && manageable ? [{ title: t`Revoke membership`, consequence: "Remove this member's access to the space. A reason is required.", action: { label: t`Revoke`, onClick: () => { setOpen(false); onRevoke(); } } }] : []} />
  </>;
}
