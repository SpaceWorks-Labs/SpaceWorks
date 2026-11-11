import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../../../components/layouts";
import { ErrorText, type QueryState, PagePager } from "../../../../components/ui";
import { isSurfaceOff } from "../../../../lib/api/errors";
import { refreshMembershipAuthority } from "../roleSets";
import { RolesReference } from "../RolesReference";
import { StaffMfaResetDialog } from "./StaffMfaResetDialog";
import { StaffRoleEditor } from "./StaffRoleEditor";
import { StaffRoleGrantDialog } from "./StaffRoleGrantDialog";
import { StaffRoleInvitations } from "./StaffRoleInvitations";
import { StaffBulkInviteDialog } from "./StaffBulkInviteDialog";
import { StaffRevokeDialog, StaffRoleRows } from "./StaffRoleRows";
import { filterStaffRows, groupStaffRows, StaffRoleFilterBar, type StaffRoleFilter } from "./staffRoleFilters";
import {
  deliveryText, invitationsKey, listSpaceRoles, listStaffInvitations, listStaffRoles, restoreStaffRole, revokeStaffRole,
  spaceRolesKey, staffRoleErrorText, staffRolesKey, type StaffRoleRow,
} from "./staffRolesApi";

/** Staff roles are rows on people's own accounts: one account per person, never a separate staff login. */
export function StaffRolesPanel({ space, toolbar, onAuthRefresh, secondary, canManageRoles = false }: {
  space: number; toolbar?: ReactNode; onAuthRefresh: () => void;
  secondary?: { label: string; onClick: () => void }; canManageRoles?: boolean;
}) {
  const client = useQueryClient();
  const [tab, setTab] = useState("staff");
  const [page, setPage] = useState(1);
  const [invitePage, setInvitePage] = useState(1);
  const [includeRevoked, setIncludeRevoked] = useState(false);
  const [adding, setAdding] = useState(false);
  const [bulkInviting, setBulkInviting] = useState(false);
  const [editing, setEditing] = useState<StaffRoleRow>();
  const [revoking, setRevoking] = useState<StaffRoleRow>();
  const [resetting, setResetting] = useState<StaffRoleRow>();
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState<StaffRoleFilter>({ role: "", grouped: false });
  const list = useQuery({ queryKey: [...staffRolesKey(space), page, includeRevoked], queryFn: () => listStaffRoles(space, page, includeRevoked), enabled: space > 0 });
  const policy = list.data?.policy;
  const tabs = [{ key: "staff", label: t`Staff` },
    ...(policy?.email_invites_available ? [{ key: "invitations", label: t`Invitations` }] : []),
    ...(canManageRoles ? [{ key: "roles", label: t`Role definitions` }] : [])];
  // Authority can change after a refresh or a makerspace switch; always render a valid tab.
  const activeTab = tabs.some(item => item.key === tab) ? tab : "staff";
  const invites = useQuery({ queryKey: [...invitationsKey(space), invitePage], queryFn: () => listStaffInvitations(space, invitePage), enabled: activeTab === "invitations" });
  const roles = useQuery({ queryKey: spaceRolesKey(space), queryFn: () => listSpaceRoles(space), enabled: activeTab === "roles" });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: staffRolesKey(space) });
    void client.invalidateQueries({ queryKey: invitationsKey(space) });
    void refreshMembershipAuthority(client, space); onAuthRefresh();
  };
  const done = (text: string) => { setNotice(text); refresh(); };
  const revoke = useMutation({ mutationFn: (row: StaffRoleRow) => revokeStaffRole(space, row.id, reason.trim()),
    onSuccess: row => { setRevoking(undefined); setReason(""); done(`${row.display_name || row.username}'s staff roles were revoked. Their account is unchanged.`); } });
  const restore = useMutation({ mutationFn: (row: StaffRoleRow) => restoreStaffRole(space, row.id),
    onSuccess: row => done(`${row.display_name || row.username}'s staff roles were restored.`) });
  // An invitation request can see the switch turn off before the roles policy refreshes.
  const invitesOff = isSurfaceOff(invites.error);
  const active = activeTab === "staff" ? list : activeTab === "invitations" ? invites : roles;
  const state: QueryState = active.isPending ? { status: "loading" }
    : active.isError && !(activeTab === "invitations" && invitesOff)
      ? { status: "error", error: staffRoleErrorText(active.error), onRetry: () => void active.refetch() } : { status: "ready" };
  const empty = activeTab === "invitations"
    ? { message: invitesOff ? t`Staff invitations are turned off for this makerspace.` : t`No staff invitations yet.` }
    : activeTab === "roles" ? { message: t`No roles to show.` }
      : { message: includeRevoked ? t`No staff here yet.` : t`No active staff here. Grant a role to a member of this space, or invite someone by email.` };
  const isEmpty = activeTab === "staff" ? list.data?.count === 0
    : activeTab === "invitations" ? invitesOff || invites.data?.count === 0 : roles.data?.length === 0;
  const actionError = activeTab === "staff" ? restore.error : null;
  const shownStaff = filterStaffRows(list.data?.results ?? [], filter.role);
  return <ListLayout tabs={tabs} activeTab={activeTab} onTabChange={key => { setTab(key); setNotice(""); }}
    header={{ title: t`Staff & roles`, secondary,
      subtitle: t`Staff roles belong to people's own accounts. Grant one to a member of this space, or invite someone by email.`,
      primary: policy?.grantable_roles.length ? { label: t`Add staff`, icon: "Plus", onClick: () => setAdding(true) } : undefined,
      // Decision 248: up to 50 email invitations in one all-or-nothing batch.
      overflow: policy?.email_invites_available && policy.grantable_roles.length ? [{ label: t`Invite several by email`, onClick: () => setBulkInviting(true) }] : undefined }}
    state={state} isEmpty={isEmpty} empty={empty}
    filters={{ toolbar: <div className="grid gap-3">{toolbar}
      {activeTab === "staff" ? <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" className="h-5 w-5 accent-accent" checked={includeRevoked} onChange={e => { setIncludeRevoked(e.target.checked); setPage(1); }} />{t`Show revoked`}</label> : null}
      {activeTab === "staff" ? <StaffRoleFilterBar policy={policy} rows={list.data?.results ?? []} value={filter} onChange={setFilter}
        partial={Boolean(list.data?.next || list.data?.previous)} /> : null}
      {notice ? <p className="text-sm text-ink" role="status">{notice}</p> : null}
      {actionError ? <ErrorText message={staffRoleErrorText(actionError)} /> : null}
    </div> }}
    body={{ kind: "rows", rows: activeTab === "roles" ? <RolesReference roles={roles.data ?? []} onShowHolders={slug => { setFilter({ role: slug, grouped: false }); setTab("staff"); }} />
      : activeTab === "invitations" ? invites.data ? <StaffRoleInvitations space={space} data={invites.data} page={invitePage}
        onPage={setInvitePage} onChanged={refresh} onNotice={setNotice} /> : null
        : <>
          {(filter.grouped ? groupStaffRows(shownStaff) : [{ area: "all", label: "", rows: shownStaff }]).map(group => <section key={group.area} className="grid gap-2" aria-label={group.label || undefined}>
            {group.label ? <h3 className="title-section">{group.label} <span className="tabular-nums text-muted">({group.rows.length})</span></h3> : null}
            <StaffRoleRows rows={group.rows} policy={policy} pending={revoke.isPending || restore.isPending}
              onEdit={setEditing} onRestore={row => restore.mutate(row)} onResetMfa={setResetting}
              onRevoke={row => { revoke.reset(); setReason(""); setRevoking(row); }} />
          </section>)}
          {filter.role && !shownStaff.length ? <p className="text-sm text-muted">{t`Nobody here holds that role.`}</p> : null}
          <PagePager page={page} setPage={setPage} next={list.data?.next} />
        </> }}
    detail={<>
      {bulkInviting && policy ? <StaffBulkInviteDialog space={space} policy={policy} onClose={() => setBulkInviting(false)}
        onDone={text => { setBulkInviting(false); done(text); }} /> : null}
      {adding && policy ? <StaffRoleGrantDialog space={space} policy={policy} onClose={() => setAdding(false)}
        onDone={(result, who) => { setAdding(false); done(result.kind === "invited" ? deliveryText(result.delivery_status) : `Staff roles granted to ${who}.`); }} /> : null}
      {editing && policy ? <StaffRoleEditor key={editing.id} space={space} policy={policy} row={editing} onClose={() => setEditing(undefined)}
        onSaved={row => { setEditing(undefined); done(`Roles updated for ${row.display_name || row.username}.`); }} /> : null}
      {revoking ? <StaffRevokeDialog row={revoking} reason={reason} onReason={setReason} pending={revoke.isPending}
        error={revoke.error ? staffRoleErrorText(revoke.error) : undefined} onClose={() => { setRevoking(undefined); revoke.reset(); }} onConfirm={() => revoke.mutate(revoking)} /> : null}
      {resetting ? <StaffMfaResetDialog key={resetting.id} space={space} row={resetting} onClose={() => setResetting(undefined)}
        onDone={() => { const name = resetting.display_name || resetting.username; setResetting(undefined);
          done(`${name}'s authenticator was reset. They set up two-step sign-in again at their next sign-in.`); }} /> : null}
    </>} />;
}
