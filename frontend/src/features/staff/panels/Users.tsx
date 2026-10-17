import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest, type StaffAuthUser } from "../../../lib/api";
import type { Makerspace } from "./shared";
import { ListLayout } from "../../../components/layouts";
import { CreateMakerspaceModal, type MakerspaceForm } from "./UsersModals";
import { emptyMakerspaceForm, makerspacePayload } from "./users/forms";
import { StaffAccountsPanel } from "./staffAccounts/StaffAccountsPanel";

/** Both the tenant console and React platform console use the same lifecycle API. */
export function Users({ makerspaces, isSuperadmin, currentUser, onAuthRefresh }: {
  makerspaces: Makerspace[]; isSuperadmin: boolean; currentUser: StaffAuthUser; onAuthRefresh: () => void;
}) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<number>();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<MakerspaceForm>(emptyMakerspaceForm);
  // Keep the created space selectable while the makerspace list refetches.
  const [createdSpace, setCreatedSpace] = useState<Makerspace>();
  useEffect(() => {
    if (createdSpace && makerspaces.some(row => row.id === createdSpace.id)) setCreatedSpace(undefined);
  }, [createdSpace, makerspaces]);
  const spaces = createdSpace && !makerspaces.some(row => row.id === createdSpace.id) ? [...makerspaces, createdSpace] : makerspaces;
  const space = spaces.find(row => row.id === selected) ?? spaces[0];
  const canManageRoles = isSuperadmin || Boolean(currentUser.makerspaces.find(row => row.id === space?.id)?.actions.includes("manage_makerspace"));
  const create = useMutation({ mutationFn: () => staffRequest<Makerspace>("/admin/makerspaces", {
    method: "POST", body: JSON.stringify(makerspacePayload(form)),
  }), onSuccess: result => {
    setCreatedSpace(result); setSelected(result.id); setCreateOpen(false); setForm(emptyMakerspaceForm);
    void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    void client.invalidateQueries({ queryKey: ["organizations"] });
  } });
  return <>
    {space ? <StaffAccountsPanel key={space.id} space={space.id} onAuthRefresh={onAuthRefresh}
      canManageRoles={canManageRoles} initialCreateRoles={createdSpace?.id === space.id ? ["space_manager"] : undefined}
      secondary={isSuperadmin ? { label: "Create makerspace", onClick: () => { create.reset(); setCreateOpen(true); } } : undefined}
      toolbar={<>
        {spaces.length > 1 ? <label className="grid gap-2 text-sm font-semibold">Makerspace<select className="desk-input" value={space.id} onChange={e => { setSelected(Number(e.target.value)); setCreatedSpace(undefined); }}>
          {spaces.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select></label> : null}
      </>} /> : <ListLayout header={{ title: "Staff & roles", primary: isSuperadmin ? { label: "Create makerspace", onClick: () => setCreateOpen(true) } : undefined }}
        state={{ status: "ready" }} isEmpty empty={{ message: "No makerspaces available for this account." }} body={{ kind: "rows", rows: null }} />}
    <CreateMakerspaceModal open={createOpen} form={form} pending={create.isPending} error={create.error}
      onChange={setForm} onClose={() => setCreateOpen(false)} onSubmit={() => create.mutate()} />
  </>;
}
