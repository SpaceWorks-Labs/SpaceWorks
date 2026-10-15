import { useState } from "react";
import { DetailLayout } from "../../components/layouts/DetailLayout";
import { ListRow, OverflowMenu, SettingsRow, StatusPill } from "../../components/ui";
import type { AdminMembership, PatchedMembershipCapabilities } from "../../generated/api";
import type { AdmissionVouch } from "../members/membershipAdmissionApi";
import { MembershipVouchers } from "./MembershipAdmissionReview";
import { PaymentReconcileActions } from "./PaymentReconcileActions";
type Role = { id: number; name: string };

export function MemberRow({ makerspaceId, member, roles, canManageMakerspace, canViewFinance, canRecordPayment, membershipEnabled, changingRole, changingCapabilities, changingVerification, changingWitness, onChangeRole, onCapability, onVerify, onWitness, onRevoke, onTerms }: {
  makerspaceId: number;
  member: AdminMembership;
  roles: Role[];
  canManageMakerspace: boolean;
  canViewFinance: boolean;
  canRecordPayment: boolean;
  membershipEnabled: boolean;
  changingRole: boolean;
  changingCapabilities: boolean;
  changingVerification: boolean;
  changingWitness: boolean;
  onChangeRole: (roleId: number) => void;
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
  return <><ListRow title={displayName} identity={{ kind: "avatar", name: displayName, seed: String(member.user.id) }} onClick={() => setOpen(true)}
    meta={<><span className="[overflow-wrap:anywhere]">{member.user.email || member.user.username}</span> · {member.assigned_role?.name ?? "Member"} · Waiver {member.waiver_required ? (member.waiver_current ? "current" : "needed") : "not required"}</>}
    right={<div className="flex flex-wrap items-center gap-2">
      <StatusPill label={member.status ?? "Unknown"} tone={active ? "success" : "neutral"} />
      {membershipEnabled ? <StatusPill tone={member.verified_at ? "success" : "neutral"} label={member.verified_at ? "Verified" : "Not verified"} /> : null}
      {/* Who owes money is roster-level information: amount, Mark offline and Waive stay on the row. */}
      {canViewFinance && member.payment?.status === "pending" ? <PaymentReconcileActions makerspaceId={makerspaceId} payment={member.payment}
        canRecordPayment={canRecordPayment || canManageMakerspace} canWaive={canManageMakerspace} invalidateKeys={[["members", makerspaceId]]} /> : null}
      {active && member.waiver_required && !member.waiver_current ? <button className="desk-button" disabled={changingWitness} onClick={onWitness}>Record witnessed acceptance</button> : null}
      {active ? <OverflowMenu label={`Actions for ${displayName}`} actions={[
        { label: "Member details", onClick: () => setOpen(true) },
        ...(membershipEnabled ? [{ label: member.verified_at ? "Unverify" : "Verify", pending: changingVerification, onClick: onVerify }, { label: "Terms", onClick: onTerms }] : []),
        ...(manageable ? [{ label: "Revoke", tone: "danger" as const, onClick: onRevoke }] : []),
      ]} /> : null}
    </div>} />
    <DetailLayout presentation="drawer" open={open} onClose={() => setOpen(false)} title={displayName}
      identity={{ kind: "avatar", name: displayName, seed: String(member.user.id) }} status={<StatusPill label={member.status ?? "Unknown"} tone={active ? "success" : "neutral"} />}
      state={{ status: "ready" }} main={<div className="grid gap-4">
        <SettingsRow label="Role" helper="The actions this member can take in this space.">{active && manageable ? <select aria-label={`Role for ${displayName}`} className="desk-input" value={member.assigned_role?.id ?? ""} disabled={changingRole} onChange={event => onChangeRole(Number(event.target.value))}>{roles.map(role => <option key={role.id} value={role.id}>{role.name}</option>)}</select> : <span>{member.assigned_role?.name ?? "Member"}</span>}</SettingsRow>
        {active && membershipEnabled ? <>
          <SettingsRow label="Can refer" helper="Can vouch for a new member."><label className="flex min-h-11 items-center gap-3"><input aria-label="Can refer" className="h-5 w-5 accent-accent" type="checkbox" checked={member.can_refer} disabled={changingCapabilities} onChange={event => onCapability({ can_refer: event.target.checked })} />Allow referrals</label></SettingsRow>
          <SettingsRow label="Can verify" helper="Can verify other members."><label className="flex min-h-11 items-center gap-3"><input aria-label="Can verify" className="h-5 w-5 accent-accent" type="checkbox" checked={member.can_verify} disabled={changingCapabilities} onChange={event => onCapability({ can_verify: event.target.checked })} />Allow verification</label></SettingsRow>
          <SettingsRow label="Verification"><button className="desk-button" disabled={changingVerification} onClick={onVerify}>{member.verified_at ? "Unverify" : "Verify"}</button></SettingsRow>
          <SettingsRow label="Membership terms"><button className="desk-button" onClick={() => { setOpen(false); onTerms(); }}>Terms</button></SettingsRow>
        </> : null}
        <SettingsRow label="Waiver"><span>{member.waiver_required ? member.waiver_current ? "Current" : "Acceptance needed" : "Not required"}</span></SettingsRow>
        <MembershipVouchers vouches={(member as AdminMembership & { vouches?: AdmissionVouch[] }).vouches} />
        {canViewFinance && member.payment?.status !== "pending" ? <PaymentReconcileActions makerspaceId={makerspaceId} payment={member.payment} canRecordPayment={canRecordPayment || canManageMakerspace} canWaive={canManageMakerspace} invalidateKeys={[["members", makerspaceId]]} /> : null}
      </div>}
      danger={active && manageable ? [{ title: "Revoke membership", consequence: "Remove this member's access to the space. A reason is required.", action: { label: "Revoke", onClick: () => { setOpen(false); onRevoke(); } } }] : []} />
  </>;
}
