import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, EmptyState, ErrorText, ListRow, OverflowMenu, Skeleton, StatusPill } from "../../../components/ui";
import { deleteRole, type Capability, type StaffRole } from "./rolesApi";
import { RoleEditor } from "./RoleEditor";
import { useStaffGet } from "./shared";

export function RoleManager({ msId, actorActions, isSuperadmin, onRolesChanged }: {
  msId: number;
  actorActions: readonly string[];
  isSuperadmin: boolean;
  onRolesChanged: () => void;
}) {
  const queryClient = useQueryClient();
  const roles = useStaffGet<StaffRole[]>(["staff", "roles", msId], `/admin/makerspaces/${msId}/roles`);
  const capabilities = useStaffGet<Capability[]>(["staff", "capabilities", msId], `/admin/makerspaces/${msId}/roles/capabilities`);
  const [editing, setEditing] = useState<StaffRole | null | undefined>();
  const [deleteError, setDeleteError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<StaffRole | null>(null);
  const labels = new Map((capabilities.data ?? []).map((item) => [item.value, item.label]));
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["staff", "roles", msId] });
    onRolesChanged();
  };
  const remove = useMutation({
    mutationFn: (role: StaffRole) => deleteRole(msId, role.id),
    onSuccess: refresh,
    onError: (error) => setDeleteError(error instanceof Error ? error.message : "Unable to delete role"),
  });

  return (
    <section aria-labelledby="roles-heading" className="rounded-xl border border-line bg-panel">
      <h2 id="roles-heading" className="title-panel px-4 py-3">Roles</h2>
      <div className="grid gap-3 border-t border-line p-3">
        <div className="flex justify-end">
          <button className="desk-button-primary" type="button" onClick={() => { setDeleteError(""); setEditing(null); }}>
            New role
          </button>
        </div>
        {roles.error ? <ErrorText resource="roles" onRetry={() => { void roles.refetch(); }} /> : null}
        {capabilities.error ? <ErrorText resource="role capabilities" onRetry={() => { void capabilities.refetch(); }} /> : null}
        {deleteError ? <ErrorText message={deleteError} /> : null}
        {roles.isLoading ? <div role="status" aria-label="Loading roles"><Skeleton className="h-24 w-full" /></div> : null}
        {!roles.isLoading && !roles.error && !roles.data?.length ? <EmptyState message="No roles yet. Create a role to share the work." /> : null}
        <div className="grid gap-2">
          {roles.data?.map((role) => (
            <ListRow key={role.id} title={role.name} identity={{ kind: "icon", icon: "User", tone: "accent" }}
              meta={<><span>{role.granted_actions.length} actions · {role.member_count} staff</span><br />{role.granted_actions.map(action => labels.get(action) ?? action).join(", ") || "No capabilities"}</>}
              onClick={() => { setDeleteError(""); setEditing(role); }}
              right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={role.is_default ? "Default" : "Custom"} />{role.is_protected ? <StatusPill label="Protected" /> : null}
                <OverflowMenu label={`Actions for ${role.name}`} actions={[{ label: "Edit", onClick: () => { setDeleteError(""); setEditing(role); } },
                  { label: "Delete", tone: "danger", disabled: role.is_protected || role.member_count > 0 || remove.isPending, disabledReason: role.is_protected ? "Default roles are protected." : role.member_count > 0 ? "Reassign all staff before deleting this role." : remove.isPending ? "Wait for the current role deletion." : undefined, onClick: () => setPendingDelete(role) }]} /></div>} />
          ))}
        </div>
      </div>
      {editing !== undefined ? <RoleEditor msId={msId} role={editing} capabilities={capabilities.data ?? []}
        catalogState={{ status: capabilities.isLoading ? "loading" : capabilities.isError ? "error" : "ready", error: "Couldn't load role capabilities. Try again.", onRetry: () => { void capabilities.refetch(); } }}
        actorActions={actorActions} isSuperadmin={isSuperadmin} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); refresh(); }} onDelete={editing ? () => { setPendingDelete(editing); setEditing(undefined); } : undefined} /> : null}
      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete role?"
        message={pendingDelete ? `Delete ${pendingDelete.name}?` : "Delete this role?"}
        confirmLabel="Delete role"
        tone="danger"
        pending={remove.isPending}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete, { onSuccess: () => setPendingDelete(null) });
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </section>
  );
}
