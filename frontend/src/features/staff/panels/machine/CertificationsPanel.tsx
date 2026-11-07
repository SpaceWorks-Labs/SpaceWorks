import { t } from "@lingui/core/macro";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog } from "../../../../components/ui";
import { certificationKeys, createCertificationType, deactivateCertificationType, getCertificationTypes, updateCertificationType, type CertificationInput, type CertificationType } from "../../certificationsApi";
import { CertificationTypeForm } from "./CertificationTypeForm";
import { CertificationGrants } from "./CertificationGrants";

export function CertificationsPanel({ makerspaceId, machineTypeId , visible = true }: { visible?: boolean; makerspaceId: number; machineTypeId: number }) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<number | null>(null);
  const [editing, setEditing] = useState<CertificationType | "new" | null>(null);
  const [deactivate, setDeactivate] = useState<number | null>(null);
  const types = useQuery({ queryKey: certificationKeys.types(makerspaceId), queryFn: () => getCertificationTypes(makerspaceId) });
  const refresh = () => client.invalidateQueries({ queryKey: certificationKeys.types(makerspaceId) });
  const save = useMutation({ mutationFn: (value: CertificationInput) => editing && editing !== "new" ? updateCertificationType(editing.id, value) : createCertificationType(makerspaceId, value), onSuccess: async () => { setEditing(null); await refresh(); } });
  const remove = useMutation({ mutationFn: deactivateCertificationType, onSuccess: async () => { setDeactivate(null); await refresh(); } });
  const rows = types.data?.filter((row) => row.machine_type === machineTypeId) ?? [];
  const initial: CertificationInput = editing && editing !== "new" ? editing : { machine_type: machineTypeId, name: "", description: "", validity_days: null, is_required_for_booking: false, is_required_for_service: false };
  if (!visible) return null;
  return <section className="grid gap-3 rounded-xl border border-line bg-panel p-3" aria-label={t`Certifications`}>
    <h3 className="title-panel">{t`Certifications`}</h3>
    {types.isLoading ? <p role="status">{t`Loading certifications…`}</p> : null}
    {types.isSuccess && !rows.length ? <EmptyState message={t`No certifications defined for this machine type.`} /> : null}
    {rows.map((row) => <article key={row.id} className="grid gap-2 rounded-lg border border-line p-3">
      <h4 className="title-section">{row.name}{!row.is_active ? " (inactive)" : ""}</h4><p className="text-sm text-muted">{row.validity_days ? t`Valid for ${row.validity_days} days` : t`No expiry`}{row.is_required_for_service ? t` · Service required` : ""}{row.is_required_for_booking ? t` · Booking required` : ""}</p>
      <div className="flex flex-wrap gap-2"><button className="desk-button-ghost" onClick={() => setSelected(selected === row.id ? null : row.id)}>{selected === row.id ? t`Hide grants` : t`View grants`}</button>{row.is_active ? <><button className="desk-button-ghost" onClick={() => setEditing(row)}>{t`Edit type`}</button><button className="desk-button-danger" onClick={() => setDeactivate(row.id)}>{t`Deactivate`}</button></> : null}</div>
      {selected === row.id ? <CertificationGrants key={row.id} typeId={row.id} active={row.is_active} /> : null}
    </article>)}
    {editing ? <CertificationTypeForm key={editing === "new" ? "new" : editing.id} initial={initial} pending={save.isPending} onSave={(value) => save.mutate(value)} onCancel={() => setEditing(null)} /> : <button className="desk-button-primary w-fit" onClick={() => setEditing("new")}>{t`New certification type`}</button>}
    {[types.error, save.error, remove.error].map((error, index) => error instanceof Error ? <p role="alert" className="text-sm text-danger" key={index}>{error.message}</p> : null)}
    <ConfirmDialog open={deactivate !== null} title={t`Deactivate certification type?`} message={t`This requirement stops gating requests and bookings. Existing training records remain.`} confirmLabel={t`Deactivate`} tone="danger" pending={remove.isPending} onConfirm={() => { if (deactivate !== null) remove.mutate(deactivate); }} onCancel={() => setDeactivate(null)} />
  </section>;
}
