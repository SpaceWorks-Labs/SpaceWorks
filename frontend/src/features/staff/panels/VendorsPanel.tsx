import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ListLayout } from "../../../components/layouts";
import { ErrorText, Field, ListRow, Modal, OverflowMenu, StatusPill } from "../../../components/ui";
import { inventoryQueryState } from "./inventoryPresentation";
import { draftFromVendor, emptyVendorDraft, vendorKeys, vendorsApi, type Vendor, type VendorDraft } from "./vendorsApi";

type Editing = { vendor: Vendor | null } | null;

/** Saved suppliers for the To-Buy list. Archive instead of delete: purchases keep their vendor link. */
export function VendorsPanel({ makerspaceId, onBack }: { makerspaceId: number; onBack: () => void }) {
  const client = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const query = useQuery({ queryKey: vendorKeys.list(makerspaceId, showArchived), queryFn: () => vendorsApi.list(makerspaceId, showArchived) });
  const rows = (query.data ?? []).filter(vendor => vendor.is_archived === showArchived);
  const invalidate = () => client.invalidateQueries({ queryKey: vendorKeys.all(makerspaceId) });
  const archive = useMutation({
    mutationFn: (vendor: Vendor) => vendorsApi.update(makerspaceId, vendor.id, { is_archived: !vendor.is_archived }),
    onSuccess: invalidate,
  });
  const add = { label: "Add vendor", onClick: () => setEditing({ vendor: null }) };
  return <ListLayout header={{ title: "Vendors", subtitle: "Suppliers you buy from, saved once and picked on every purchase.",
    primary: add, secondary: { label: "Back to To-Buy", onClick: onBack } }}
    tabs={[{ key: "active", label: "Active" }, { key: "archived", label: "Archived" }]} activeTab={showArchived ? "archived" : "active"}
    onTabChange={key => setShowArchived(key === "archived")}
    state={inventoryQueryState(query, "vendors")} isEmpty={!rows.length} filtered={showArchived}
    empty={{ message: "No vendors yet. Add the shops and suppliers you buy from.", action: add }}
    filteredEmpty={{ message: "No archived vendors.", action: { label: "Show active", onClick: () => setShowArchived(false) } }}
    body={{ kind: "rows", rows: <>{rows.map(vendor => <ListRow key={vendor.id} title={vendor.name}
      identity={{ kind: "avatar", name: vendor.name, seed: `vendor-${vendor.id}` }}
      meta={[vendor.contact_name, vendor.email, vendor.phone].filter(Boolean).join(" · ") || "No contact details"}
      right={<div className="flex flex-wrap items-center gap-2">
        {vendor.is_archived ? <StatusPill label="Archived" /> : null}
        <OverflowMenu label={`Actions for ${vendor.name}`} actions={[
          { label: "Edit", onClick: () => setEditing({ vendor }) },
          vendor.is_archived ? { label: "Restore", disabled: archive.isPending, onClick: () => archive.mutate(vendor) }
            : { label: "Archive", disabled: archive.isPending, onClick: () => archive.mutate(vendor),
              confirm: { title: `Archive ${vendor.name}?`, message: "It leaves the vendor picker. Past purchases keep their link, and you can restore it later.", confirmLabel: "Archive" } },
        ]} />
      </div>} />)}<ErrorText message={archive.error?.message} /></> }}
    detail={editing ? <VendorDialog key={editing.vendor?.id ?? "new"} makerspaceId={makerspaceId} vendor={editing.vendor}
      onClose={() => setEditing(null)} onSaved={() => { void invalidate(); setEditing(null); }} /> : null} />;
}

const FIELDS: { key: keyof VendorDraft; label: string; type?: string; max: number }[] = [
  { key: "contact_name", label: "Contact person", max: 200 },
  { key: "email", label: "Email", type: "email", max: 254 },
  { key: "phone", label: "Phone", type: "tel", max: 40 },
  { key: "website", label: "Website", type: "url", max: 200 },
];

function VendorDialog({ makerspaceId, vendor, onClose, onSaved }: { makerspaceId: number; vendor: Vendor | null; onClose: () => void; onSaved: () => void }) {
  const [draft, setDraft] = useState<VendorDraft>(vendor ? draftFromVendor(vendor) : emptyVendorDraft);
  const save = useMutation({
    mutationFn: () => vendor ? vendorsApi.update(makerspaceId, vendor.id, draft) : vendorsApi.create(makerspaceId, draft),
    onSuccess: onSaved,
  });
  const set = (key: keyof VendorDraft) => (event: { target: { value: string } }) => setDraft({ ...draft, [key]: event.target.value });
  return <Modal open onClose={onClose} title={vendor ? `Edit ${vendor.name}` : "Add vendor"}>
    <form className="grid gap-4 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); if (draft.name.trim()) save.mutate(); }}>
      <Field label="Company name" className="sm:col-span-2"><input className="desk-input" required maxLength={200} value={draft.name} onChange={set("name")} /></Field>
      {FIELDS.map(field => <Field key={field.key} label={field.label}><input className="desk-input" type={field.type ?? "text"} maxLength={field.max} value={draft[field.key]} onChange={set(field.key)} /></Field>)}
      <Field label="Notes" className="sm:col-span-2"><textarea className="desk-input min-h-20" value={draft.notes} onChange={set("notes")} /></Field>
      <div className="sm:col-span-2"><ErrorText message={save.error?.message} /></div>
      <div className="flex flex-wrap justify-end gap-2 sm:col-span-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="desk-button-primary" disabled={!draft.name.trim() || save.isPending}>{save.isPending ? "Saving…" : vendor ? "Save vendor" : "Add vendor"}</button>
      </div>
    </form>
  </Modal>;
}
