import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../../components/layouts";
import { ErrorText, Field, ListRow, Modal, StatusBadge, StatusPill } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { inventoryQueryState } from "./inventoryPresentation";
import { type Makerspace, useStaffGet } from "./shared";
import {
  CONSUMABLES_PAGE_SIZE, SOURCE_LABELS, SOURCE_TONES, consumableKeys, consumablesPath, logConsumableUse, unitLabel,
  type ConsumablePage, type ConsumableRow, type ConsumableStatus,
} from "./consumablesApi";

const STATUSES: { key: ConsumableStatus; label: string }[] = [
  { key: "all", label: "All" }, { key: "low", label: "Running low" }, { key: "ok", label: "Stocked" },
];

/** Everything the space uses up, in one list: item consumables, per-machine consumables and material pools. */
export function ConsumablesPanel({ makerspace, canEditInventory = false }: { makerspace: Makerspace; canEditInventory?: boolean }) {
  const [params, setParams] = useSearchParams();
  const raw = params.get("status");
  const status: ConsumableStatus = raw === "low" || raw === "ok" ? raw : "all";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [usingRow, setUsingRow] = useState<ConsumableRow | null>(null);
  const query = useStaffGet<ConsumablePage>([...consumableKeys.list(makerspace.id, status, page)], consumablesPath(makerspace.id, status, page));
  const rows = query.data?.results ?? [];
  const href = (next: ConsumableStatus) => { const search = new URLSearchParams(params); search.set("status", next); search.delete("page"); return `?${search}`; };
  const toBuyHref = `/m/${makerspace.slug}/admin/to-buy?status=all`;
  return <ListLayout header={{ title: "Consumables", subtitle: "What the space uses up, and what is running low." }}
    tabs={STATUSES.map(option => ({ key: option.key, label: option.label, href: href(option.key) }))} activeTab={status}
    state={inventoryQueryState(query, "consumables")} isEmpty={!rows.length} filtered={status !== "all"}
    empty={{ message: "No consumables yet. Mark a quantity-tracked item as a consumable in its details." }}
    filteredEmpty={{ message: status === "low" ? "Nothing is running low." : "Nothing is fully stocked right now.", action: { label: "View all", href: href("all") } }}
    body={{ kind: "rows", rows: rows.map(row => <ConsumableListRow key={`${row.source}-${row.id}`} row={row} toBuyHref={toBuyHref}
      onUse={row.source === "item" && canEditInventory ? () => setUsingRow(row) : undefined} />) }}
    pagination={query.data && query.data.count > CONSUMABLES_PAGE_SIZE ? { page, pageSize: CONSUMABLES_PAGE_SIZE, count: query.data.count,
      onChange: next => setParams(current => { const search = new URLSearchParams(current); search.set("page", String(next)); return search; }) } : undefined}
    detail={usingRow ? <LogUseDialog key={usingRow.id} row={usingRow} makerspaceId={makerspace.id} onClose={() => setUsingRow(null)} /> : null} />;
}

function ConsumableListRow({ row, toBuyHref, onUse }: { row: ConsumableRow; toBuyHref: string; onUse?: () => void }) {
  const threshold = row.threshold === null ? "No reorder level" : `reorder at ${row.threshold}`;
  return <ListRow title={row.name} identity={{ kind: "icon", icon: row.status === "low" ? "TriangleAlert" : "Circle", tone: row.status === "low" ? "emphasis" : SOURCE_TONES[row.source] }}
    meta={<><span className="tabular-nums">{row.remaining} {unitLabel(row.unit)}</span> · {threshold}{row.machine_name ? ` · ${row.machine_name}` : ""}</>}
    right={<div className="flex flex-wrap items-center gap-2">
      <StatusPill label={SOURCE_LABELS[row.source]} tone={SOURCE_TONES[row.source]} />
      {row.status === "low" ? <StatusBadge status="low" label="Low" /> : null}
      {row.open_to_buy_id ? <RouteLink className="inline-flex min-h-11 items-center px-1 text-sm font-semibold text-accent-ink underline" href={toBuyHref}>Open To-Buy</RouteLink> : null}
      {onUse ? <button type="button" className="desk-button" onClick={onUse}>Log use</button> : null}
    </div>} />;
}

function LogUseDialog({ row, makerspaceId, onClose }: { row: ConsumableRow; makerspaceId: number; onClose: () => void }) {
  const client = useQueryClient();
  const [quantity, setQuantity] = useState("1");
  const [note, setNote] = useState("");
  const amount = Number(quantity);
  const valid = Number.isInteger(amount) && amount >= 1;
  const use = useMutation({
    mutationFn: () => logConsumableUse(makerspaceId, row.id, amount, note.trim()),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: consumableKeys.all(makerspaceId) });
      void client.invalidateQueries({ queryKey: ["inventory", makerspaceId] });
      onClose();
    },
  });
  return <Modal open onClose={onClose} title={`Log use of ${row.name}`}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (valid) use.mutate(); }}>
      <p className="text-sm text-muted"><span className="tabular-nums">{row.remaining}</span> {unitLabel(row.unit)}. Used stock is never lent and does not come back.</p>
      <Field label="How many were used"><input className="desk-input" type="number" min={1} step={1} required value={quantity} onChange={event => setQuantity(event.target.value)} /></Field>
      <Field label="Note (optional)"><input className="desk-input" maxLength={200} value={note} onChange={event => setNote(event.target.value)} /></Field>
      <ErrorText message={use.error?.message} />
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="desk-button-primary" disabled={!valid || use.isPending}>{use.isPending ? "Saving…" : "Log use"}</button>
      </div>
    </form>
  </Modal>;
}
