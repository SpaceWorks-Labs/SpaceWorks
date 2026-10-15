import { useState } from "react";
import { ConfirmDialog } from "../../components/ui";
import { useDeleteOrganization } from "../organizations/organizationSelfServiceApi";
import type { OrganizationDetail } from "./organizationsApi";

export function OrganizationDelete({ organization, onDeleted }: { organization: OrganizationDetail; onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const remove = useDeleteOrganization(organization.id);
  if (!["manage_organization_members", "manage_organization_profile"].every(action => organization.governance_actions.includes(action))) return null;
  return <section className="grid gap-3 rounded border border-line p-4">
    <h3 className="title-section">Delete organization</h3>
    <p className="text-sm text-muted">Deletion requires recent identity verification. Linked makerspaces, event references, or retained artwork prevent deletion. Memberships and invitations are removed; the audit history remains.</p>
    <button className="desk-button-danger" type="button" onClick={() => setOpen(true)} disabled={remove.isPending}>Delete organization</button>
    {remove.error ? <p role="alert" className="text-danger">{remove.error.message}</p> : null}
    <ConfirmDialog open={open} title={`Delete ${organization.name}?`} message="This permanently removes this unlinked organization, its memberships and invitations." confirmLabel="Delete organization" pending={remove.isPending} onCancel={() => setOpen(false)} onConfirm={() => remove.mutate(undefined, { onSuccess: () => { setOpen(false); onDeleted(); } })} />
  </section>;
}
