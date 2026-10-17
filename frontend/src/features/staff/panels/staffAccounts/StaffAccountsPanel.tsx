import { StaffStatusDialog } from "./StaffStatusDialog";
import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../../../components/layouts";
import { ErrorText } from "../../../../components/ui";
import { deactivateStaffAccount, listStaffAccounts, reactivateStaffAccount, resendStaffInvite, staffAccountPolicy, type StaffAccount, type StaffRoleKey } from "../../../../lib/api/staffAccounts";
import { StaffAccountEditor } from "./StaffAccountEditor";
import { StaffAccountRows } from "./StaffAccountRows";
import { StaffPasswordDialog } from "./StaffPasswordDialog";
import { refreshMembershipAuthority } from "../roleSets";
import { useStaffGet } from "../shared";
import type { StaffRole } from "../rolesApi";
import { RolesReference } from "../RolesReference";

export function StaffAccountsPanel({ space, toolbar, onAuthRefresh, secondary, canManageRoles = false, initialCreateRoles }: {
  space: number; toolbar?: ReactNode; onAuthRefresh: () => void;
  secondary?: { label: string; onClick: () => void };
  canManageRoles?: boolean; initialCreateRoles?: StaffRoleKey[];
}) {
  const client = useQueryClient();
  const key = ["staff-accounts", space];
  const [page, setPage] = useState(1);
  const [inactive, setInactive] = useState(true);
  const [editor, setEditor] = useState<StaffAccount | "create" | undefined>(initialCreateRoles ? "create" : undefined);
  const [createRoles, setCreateRoles] = useState<StaffRoleKey[]>(initialCreateRoles ?? []);
  const [tab, setTab] = useState("staff");
  const tabs = [{ key: "staff", label: "Staff accounts", href: "#staff" },
    ...(canManageRoles ? [{ key: "roles", label: "Roles", href: "#roles" }] : [])];
  // Authority can change after a refresh or makerspace switch; always render a valid body.
  const activeTab = tabs.some(item => item.key === tab) ? tab : "staff";
  const [password, setPassword] = useState<StaffAccount>();
  const [status, setStatus] = useState<StaffAccount>();
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const list = useQuery({ queryKey: [...key, page, inactive], queryFn: () => listStaffAccounts(space, page, inactive), enabled: space > 0 });
  const policy = useQuery({ queryKey: ["staff-account-policy", space], queryFn: () => staffAccountPolicy(space), enabled: space > 0 });
  const roles = useStaffGet<StaffRole[]>(["staff", "roles", space], `/admin/makerspaces/${space}/roles`, space > 0 && canManageRoles);
  const activeQuery = activeTab === "roles" ? roles : list;
  const refresh = () => {
    void client.invalidateQueries({ queryKey: key });
    void client.invalidateQueries({ queryKey: ["staff-account-policy", space] });
    void refreshMembershipAuthority(client, space); onAuthRefresh();
  };
  const changeStatus = useMutation({ mutationFn: (account: StaffAccount) => account.is_active
    ? deactivateStaffAccount(space, account.id, reason.trim()) : reactivateStaffAccount(space, account.id),
  onSuccess: account => { setStatus(undefined); setReason(""); setNotice(account.is_active ? "Account reactivated. Issue a new password before sign-in; previous sessions and invitations stay revoked." : "Account deactivated. Its history is kept."); refresh(); } });
  const resend = useMutation({ mutationFn: (account: StaffAccount) => resendStaffInvite(space, account.id),
    onSuccess: result => { setNotice(result.invitation_sent ? "Invitation sent." : "Invitation could not be sent. You can issue a password directly."); refresh(); } });
  const error = activeQuery.error ?? (activeTab === "staff" ? policy.error ?? changeStatus.error ?? resend.error : null);
  return <ListLayout tabs={tabs} activeTab={activeTab} onTabChange={setTab}
    header={{ title: "Staff & roles", subtitle: "Separate staff accounts for this makerspace.", secondary,
    primary: policy.data?.creatable_roles.length ? { label: "Create staff account", onClick: () => { setCreateRoles([]); setEditor("create"); } } : undefined }}
    state={{ status: activeQuery.isPending || (activeTab === "staff" && policy.isPending) ? "loading" : activeQuery.isError || (activeTab === "staff" && policy.isError) ? "error" : "ready",
      error: error?.message, onRetry: () => { void activeQuery.refetch(); if (activeTab === "staff") void policy.refetch(); } }}
    filters={{ toolbar: <div className="grid gap-3">{toolbar}
      {activeTab === "staff" ? <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={inactive} onChange={e => { setInactive(e.target.checked); setPage(1); }} />Include inactive accounts</label> : null}
      {notice ? <p className="text-sm text-ink" role="status">{notice}</p> : null}
      {error && !activeQuery.isError && !(activeTab === "staff" && policy.isError) ? <ErrorText message={error.message} /> : null}
    </div> }}
    isEmpty={activeTab === "staff" && list.data?.count === 0} empty={{ message: "No staff accounts yet." }}
    body={{ kind: "rows", rows: activeTab === "roles" ? <RolesReference roles={roles.data ?? []} /> : <>
      <StaffAccountRows rows={list.data?.results ?? []} pending={changeStatus.isPending || resend.isPending} onEdit={setEditor}
        onPassword={setPassword} onStatus={account => { changeStatus.reset(); setReason(""); setStatus(account); }} onResend={account => resend.mutate(account)} />
      <div className="flex items-center gap-3"><button className="desk-button" disabled={!list.data?.previous} onClick={() => setPage(value => value - 1)}>Previous</button>
        <span className="text-sm text-muted">Page {page}</span>
        <button className="desk-button" disabled={!list.data?.next} onClick={() => setPage(value => value + 1)}>Next</button></div>
    </> }}
    detail={<>
      {editor && policy.data ? <StaffAccountEditor space={space} policy={policy.data} account={editor === "create" ? undefined : editor}
        initialRoles={createRoles}
        onClose={() => setEditor(undefined)} onSaved={(account, invitationSent) => {
          setEditor(undefined); refresh();
          if (invitationSent !== undefined) {
            setNotice(invitationSent ? "Staff account created. Invitation sent." : "Staff account created. Issue a password to complete onboarding.");
            if (!invitationSent && account.can.set_password) setPassword(account);
          }
        }} /> : null}
      {password ? <StaffPasswordDialog key={password.id} space={space} account={password} onClose={() => setPassword(undefined)} onSaved={refresh} /> : null}
      {status ? <StaffStatusDialog account={status} pending={changeStatus.isPending} reason={reason} onReason={setReason}
        error={changeStatus.error} onClose={() => setStatus(undefined)} onConfirm={() => changeStatus.mutate(status)} /> : null}
    </>} />;
}
