import { DetailLayout } from "../../../components/layouts";
import { useEffect, useState } from "react";

import { Badge, ConfirmDialog, ErrorText, Field, ListRow, OverflowMenu, RelativeTime, SettingsActions, StatusPill } from "../../../components/ui";
import { ProcurementReceipts, type ToBuyReceipt } from "./ProcurementReceipts";

export type Kind = "hardware" | "printing";
export type ToBuyStatus = "requested" | "approved" | "ordered" | "received" | "cancelled";

export type ToBuyItem = {
  id: number;
  kind: Kind;
  machine_type: number | null;
  machine_type_name: string | null;
  name: string;
  quantity: number;
  link: string;
  status: ToBuyStatus;
  estimated_unit_cost: string | null;
  vendor_name: string;
  actual_unit_cost: string | null;
  purchaser_username: string | null;
  ordered_at: string | null;
  received_at: string | null;
  moved_to_inventory_at: string | null;
  resulting_product: number | null;
  resulting_pool: number | null;
  resulting_machine: number | null;
  source_pool: number | null;
  created_by_username: string | null;
  receipts: ToBuyReceipt[];
};

export type RowDraft = {
  status: ToBuyStatus;
  vendor_name: string;
  actual_unit_cost: string;
};

export const statusOptions: ToBuyStatus[] = ["requested", "approved", "ordered", "received", "cancelled"];

export type ProcurementGroup = {
  key: string;
  label: string;
  rows: ToBuyItem[];
};

export function groupProcurementRows(rows: ToBuyItem[]): ProcurementGroup[] {
  const groups = new Map<string, ProcurementGroup>();
  for (const item of rows) {
    const key = item.machine_type === null ? "unassigned" : `type-${item.machine_type}`;
    const label = item.machine_type_name ?? "Unassigned";
    const group = groups.get(key) ?? { key, label, rows: [] };
    group.rows.push(item);
    groups.set(key, group);
  }
  return [...groups.values()].sort((left, right) => {
    if (left.key === "unassigned") return 1;
    if (right.key === "unassigned") return -1;
    return left.label.localeCompare(right.label);
  });
}

export function ProcurementRow({ item, makerspaceSlug, updatePending, deletePending, onSave, onDelete, onMove, onReceiptsChanged, updateError, deleteError }: {
  item: ToBuyItem;
  makerspaceSlug: string;
  updatePending: boolean;
  deletePending: boolean;
  onSave: (draft: RowDraft) => void;
  onDelete: () => void;
  onMove: () => void;
  onReceiptsChanged: () => void;
  updateError?: string;
  deleteError?: string;
}) {
  const [draft, setDraft] = useState<RowDraft>(() => draftFromItem(item));

  useEffect(() => setDraft(draftFromItem(item)), [item]);

  const [open, setOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const next = ({ requested: "approved", approved: "ordered", ordered: "received" } as Partial<Record<ToBuyStatus, ToBuyStatus>>)[item.status];
  const nextLabel = ({ requested: "Approve", approved: "Mark ordered", ordered: "Mark received" } as Partial<Record<ToBuyStatus, string>>)[item.status];
  return <>
    <ListRow title={`${item.name} ×${item.quantity}`} onClick={() => setOpen(true)} identity={{ kind: "icon", icon: "Circle", tone: "accent" }}
      meta={<>{item.vendor_name || "No vendor yet"} · Est. {item.estimated_unit_cost ?? "—"} each · {item.purchaser_username || "Unassigned purchaser"}{item.source_pool ? <Badge tone="warn">Auto · low stock</Badge> : null}</>}
      right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={labelStatus(item.status)} tone={item.status === "received" ? "success" : "neutral"} />
        {next ? <button className="desk-button-ghost" disabled={updatePending} onClick={() => onSave({ ...draftFromItem(item), status: next })}>{updatePending ? "Saving…" : nextLabel}</button> : item.status === "received" && !item.moved_to_inventory_at ? <button className="desk-button-ghost" onClick={onMove}>Move to inventory</button> : null}
        <OverflowMenu label={`Actions for ${item.name}`} actions={[{ label: "Edit", onClick: () => setOpen(true) }, { label: "Delete", confirms: true, tone: "danger", disabled: deletePending, onClick: () => setConfirmDelete(true) }]} />
      </div>} />
    <DetailLayout presentation="drawer" open={open} onClose={() => setOpen(false)} title={item.name} status={<StatusPill label={labelStatus(item.status)} />} state={{ status: "ready" }}
      meta={[`${item.quantity} units · ${item.kind}`, item.machine_type_name ?? "Unassigned"]}
      main={<div className="grid gap-4"><ItemLink link={item.link} />
        <p className="text-sm text-muted">Estimated unit cost: {item.estimated_unit_cost ?? "—"} · Purchaser: {item.purchaser_username ?? "Unassigned"}</p>
        {item.ordered_at ? <p>Ordered <RelativeTime date={item.ordered_at} /></p> : null}{item.received_at ? <p>Received <RelativeTime date={item.received_at} /></p> : null}
        <Field label={`Vendor for ${item.name}`}><input className="desk-input" value={draft.vendor_name} onChange={event => setDraft({ ...draft, vendor_name: event.target.value })} /></Field>
        <Field label={`Actual unit cost for ${item.name}`}><input className="desk-input" type="number" min={0} step="0.01" value={draft.actual_unit_cost} onChange={event => setDraft({ ...draft, actual_unit_cost: event.target.value })} /></Field>
        <Field label={`Status for ${item.name}`}><select className="desk-input" value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value as ToBuyStatus })}>{statusOptions.map(status => <option key={status} value={status}>{labelStatus(status)}</option>)}</select></Field>
        <MoveState item={item} makerspaceSlug={makerspaceSlug} />
        <ProcurementReceipts itemId={item.id} receipts={item.receipts ?? []} onChanged={onReceiptsChanged} />
        <ErrorText message={updateError} />
        {isDraftChanged(item, draft) ? <SettingsActions onDiscard={() => setDraft(draftFromItem(item))} onSave={() => onSave(draft)} pending={updatePending} /> : null}
      </div>} />
    <ConfirmDialog open={confirmDelete} onCancel={() => setConfirmDelete(false)} onConfirm={onDelete} title={`Delete ${item.name}?`} message="This removes the item and its receipts from the shopping list." confirmLabel="Delete" tone="danger" pending={deletePending} />
    <ErrorText message={deleteError || (!open ? updateError : undefined)} />
  </>;
}

function MoveState({ item, makerspaceSlug }: { item: ToBuyItem; makerspaceSlug: string }) {
  if (!item.moved_to_inventory_at) return <>-</>;
  if (item.resulting_product) {
    return <a className="text-accent-ink underline" href={`/m/${makerspaceSlug}/admin/inventory`}>Inventory #{item.resulting_product}</a>;
  }
  if (item.resulting_pool) return <>Pool #{item.resulting_pool}</>;
  if (item.resulting_machine) return <>Machine #{item.resulting_machine}</>;
  return <>Moved</>;
}

function ItemLink({ link }: { link: string }) {
  const href = safeHref(link);
  if (href) return <a className="text-accent-ink underline" href={href} target="_blank" rel="noreferrer">Open supplier link ↗</a>;
  if (link) return <span className="block max-w-56 break-all text-muted" title={link}>{link}</span>;
  return <>-</>;
}

function safeHref(link: string): string | null {
  return /^https?:\/\//i.test(link) ? link : null;
}

function draftFromItem(item: ToBuyItem): RowDraft {
  return {
    status: item.status,
    vendor_name: item.vendor_name ?? "",
    actual_unit_cost: item.actual_unit_cost ?? "",
  };
}

function isDraftChanged(item: ToBuyItem, draft: RowDraft) {
  return item.status !== draft.status || (item.vendor_name ?? "") !== draft.vendor_name || (item.actual_unit_cost ?? "") !== draft.actual_unit_cost;
}

export function itemTotal(item: ToBuyItem, mode: "estimated" | "actual") {
  const raw = mode === "actual" ? item.actual_unit_cost ?? item.estimated_unit_cost : item.estimated_unit_cost;
  const unitCost = Number(raw ?? 0);
  return Number.isFinite(unitCost) ? unitCost * item.quantity : 0;
}

export function labelStatus(status: ToBuyStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1).replace("_", " ");
}
