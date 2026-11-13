import { t } from "@lingui/core/macro";
import { DetailLayout } from "../../../components/layouts";
import { useEffect, useState } from "react";

import { Badge, ConfirmDialog, ErrorText, Field, ListRow, OverflowMenu, RelativeTime, SettingsActions, StatusPill } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { ProcurementReceipts, type ToBuyReceipt } from "./ProcurementReceipts";
import { BoxArt } from "../../../components/BoxSpinner";

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
  // Lane L12: the saved vendor and the machine consumable that raised the row (refilled on "Mark bought").
  vendor?: number | null;
  source_consumable?: number | null;
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

export function ProcurementRow({ item, makerspaceSlug, updatePending, deletePending, onSave, onDelete, onMove, onReceiptsChanged, updateError, deleteError, onMarkBought }: {
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
  onMarkBought?: () => void;
}) {
  const [draft, setDraft] = useState<RowDraft>(() => draftFromItem(item));

  useEffect(() => setDraft(draftFromItem(item)), [item]);

  const [open, setOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const next = ({ requested: "approved", approved: "ordered", ordered: "received" } as Partial<Record<ToBuyStatus, ToBuyStatus>>)[item.status];
  const nextLabel = ({ requested: "Approve", approved: "Mark ordered", ordered: "Mark received" } as Partial<Record<ToBuyStatus, string>>)[item.status];
  const receiptCount = item.receipts?.length ?? 0;
  // Receiving is when the actual cost and receipt are known, so it opens the drawer pre-set to Received instead of saving blind.
  const advance = () => {
    if (next === "received") { setDraft({ ...draftFromItem(item), status: "received" }); setOpen(true); }
    else if (next) onSave({ ...draftFromItem(item), status: next });
  };
  const cancellable = item.status !== "received" && item.status !== "cancelled";
  return <>
    <ListRow title={`${item.name} ×${item.quantity}`} onClick={() => setOpen(true)} identity={{ kind: "icon", icon: "Circle", tone: "accent" }}
      meta={<>{item.vendor_name || t`No vendor yet`} {t` · Est. ${item.estimated_unit_cost ?? "—"} each · `}{item.purchaser_username || t`Unassigned purchaser`} · {receiptCount === 1 ? t`1 receipt` : `${receiptCount} receipts`}{item.source_pool ? <Badge tone="warn">{t`Auto · low stock`}</Badge> : null}</>}
      right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={labelStatus(item.status)} tone={item.status === "received" ? "success" : "neutral"} />
        {next ? <button className="desk-button-ghost" disabled={updatePending} onClick={advance}>{updatePending ? <><BoxArt size={16} mono />{t`Saving…`}</> : nextLabel}</button> : item.status === "received" && !item.moved_to_inventory_at ? <button className="desk-button-ghost" onClick={onMove}>{item.source_consumable ? t`Refill consumable` : t`Move to inventory`}</button> : null}
        <OverflowMenu label={t`Actions for ${item.name}`} actions={[{ label: t`Edit`, onClick: () => setOpen(true) },
          ...(onMarkBought && next ? [{ label: t`Mark bought`, onClick: onMarkBought }] : []),
          ...(cancellable ? [{ label: t`Cancel request`, disabled: updatePending, onClick: () => onSave({ ...draftFromItem(item), status: "cancelled" as const }),
            confirm: { title: t`Cancel ${item.name}?`, message: t`It moves to Cancelled. You can reopen it from the drawer by changing its status.`, confirmLabel: t`Cancel request` } }] : []),
          { label: t`Delete`, confirms: true, tone: "danger", disabled: deletePending, onClick: () => setConfirmDelete(true) }]} />
      </div>} />
    <DetailLayout presentation="drawer" open={open} onClose={() => setOpen(false)} title={item.name} status={<StatusPill label={labelStatus(item.status)} />} state={{ status: "ready" }}
      meta={[`${item.quantity} units · ${item.kind}`, item.machine_type_name ?? "Unassigned"]}
      main={<div className="grid gap-4"><ItemLink link={item.link} />
        {draft.status === "received" && item.status !== "received" ? <p className="text-sm text-muted">{t`Record the actual unit cost and attach the receipt, then save to mark it received.`}</p> : null}
        <p className="text-sm text-muted">{t`Estimated unit cost: ${item.estimated_unit_cost ?? "—"} · Purchaser: `}{item.purchaser_username ?? t`Unassigned`}</p>
        {item.ordered_at ? <p>{t`Ordered `}<RelativeTime date={item.ordered_at} /></p> : null}{item.received_at ? <p>{t`Received `}<RelativeTime date={item.received_at} /></p> : null}
        <Field label={t`Vendor for ${item.name}`}><input className="desk-input" value={draft.vendor_name} onChange={event => setDraft({ ...draft, vendor_name: event.target.value })} /></Field>
        <Field label={t`Actual unit cost for ${item.name}`}><input className="desk-input" type="number" min={0} step="any" value={draft.actual_unit_cost} onChange={event => setDraft({ ...draft, actual_unit_cost: event.target.value })} /></Field>
        <Field label={t`Status for ${item.name}`}><select className="desk-input" value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value as ToBuyStatus })}>{statusOptions.map(status => <option key={status} value={status}>{labelStatus(status)}</option>)}</select></Field>
        <MoveState item={item} makerspaceSlug={makerspaceSlug} />
        <ProcurementReceipts itemId={item.id} receipts={item.receipts ?? []} onChanged={onReceiptsChanged} />
        <ErrorText message={updateError} />
        {isDraftChanged(item, draft) ? <SettingsActions onDiscard={() => setDraft(draftFromItem(item))} onSave={() => onSave(draft)} pending={updatePending} /> : null}
      </div>} />
    <ConfirmDialog open={confirmDelete} onCancel={() => setConfirmDelete(false)} onConfirm={onDelete} title={t`Delete ${item.name}?`} message={t`This removes the item and its receipts from the shopping list.`} confirmLabel={t`Delete`} tone="danger" pending={deletePending} />
    <ErrorText message={deleteError || (!open ? updateError : undefined)} />
  </>;
}

function MoveState({ item, makerspaceSlug }: { item: ToBuyItem; makerspaceSlug: string }) {
  if (!item.moved_to_inventory_at) return <>-</>;
  if (item.resulting_product) {
    return <RouteLink className="text-accent-ink underline" href={`/m/${makerspaceSlug}/admin/inventory?item=${item.resulting_product}`}>{t`Inventory #${item.resulting_product}`}</RouteLink>;
  }
  if (item.resulting_pool) return <>{t`Pool #${item.resulting_pool}`}</>;
  if (item.resulting_machine) return <>{t`Machine #${item.resulting_machine}`}</>;
  return <>{t`Moved`}</>;
}

function ItemLink({ link }: { link: string }) {
  const href = safeHref(link);
  if (href) return <a className="text-accent-ink underline" href={href} target="_blank" rel="noreferrer">{t`Open supplier link ↗`}</a>;
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
