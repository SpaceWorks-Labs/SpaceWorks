import { useState } from "react";
import { useUrlListState } from "../../../lib/useUrlListState";

import { Field, ListRow, RelativeTime, type IconName } from "../../../components/ui";
import { WarrantyStatusBadge } from "../WarrantyStatusBadge";
import { WarrantySection } from "../WarrantySection";
import type { WarrantyReportRow, WarrantyStatus } from "../warrantyApi";
import { ListLayout, DetailLayout } from "../../../components/layouts";
import { useSearchParams } from "react-router-dom";
import { inventoryQueryState } from "./inventoryPresentation";
import { type Makerspace, useStaffGet } from "./shared";

type WarrantyResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: WarrantyReportRow[];
};

type StatusFilter = "all" | WarrantyStatus;

const PAGE_SIZE = 50;

export function WarrantyPanel({
  makerspace,
  canEditInventory,
}: {
  makerspace: Makerspace;
  canEditInventory: boolean;
}) {
  const [params] = useSearchParams();
  const list = useUrlListState({ status: "all", missing_docs: "false", expires_before: "", page: "1" });
  const status = list.values.status as StatusFilter;
  const missingDocs = list.values.missing_docs === "true";
  const expiresBefore = list.values.expires_before;
  const page = list.page;
  const setPage = list.setPage;
  const [expanded, setExpanded] = useState<string | null>(null);
  const canManageRow = (row: WarrantyReportRow) => {
    if (row.host_kind === "asset") return canEditInventory;
    if (row.host_kind === "printer") return false;
    return true;
  };
  const queryParams = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (status !== "all") queryParams.set("status", status);
  if (missingDocs) queryParams.set("missing_docs", "true");
  if (expiresBefore) queryParams.set("expires_before", expiresBefore);
  const warranties = useStaffGet<WarrantyResponse>(
    ["warranties", makerspace.id, page, PAGE_SIZE, status, missingDocs, expiresBefore],
    `/admin/makerspace/${makerspace.id}/warranties?${queryParams.toString()}`,
  );

  const visibleRows = warranties.data?.results ?? [];
  const filtersActive = status !== "all" || missingDocs || Boolean(expiresBefore);

  const href = (value: string) => { const next = new URLSearchParams(params); next.set("status", value); next.delete("page"); return `?${next}`; };
  const selected = visibleRows.find(row => `${row.host_kind}-${row.host_id}` === expanded);
  return <ListLayout header={{ title: "Warranties", subtitle: `Coverage for equipment you can manage in ${makerspace.name}.`, meta: `${warranties.data?.count ?? 0} hosts` }}
    state={inventoryQueryState(warranties, "warranties")} isEmpty={!visibleRows.length} filtered={filtersActive}
    empty={{ message: "No warranties recorded yet. Add one from a machine or asset." }}
    filteredEmpty={{ message: "Nothing matches these filters.", action: { label: "Clear filters", onClick: () => list.restore({}) } }}
    tabs={["all", "active", "expiring_soon", "expired", "unknown"].map(key => ({ key, label: ({ all: "All", active: "Active", expiring_soon: "Expiring soon", expired: "Expired", unknown: "Not covered" } as Record<string, string>)[key], href: href(key) }))} activeTab={status}
    filters={{ views: <button type="button" className={missingDocs ? "desk-button-primary" : "desk-button"} aria-pressed={missingDocs} onClick={() => list.setFilter("missing_docs", String(!missingDocs))}>Missing docs</button>,
      controls: <Field label="Expires before"><input className="desk-input" type="date" value={expiresBefore} onChange={event => list.setFilter("expires_before", event.target.value)} /></Field>,
      activeCount: expiresBefore ? 1 : 0,
      chips: expiresBefore ? [{ key: "expires_before", label: `expires before ${expiresBefore}`, onRemove: () => list.setFilter("expires_before", "") }] : [] }}
    body={{ kind: "rows", rows: visibleRows.map(row => <ListRow key={`${row.host_kind}-${row.host_id}`} title={row.host_label}
      identity={{ kind: "icon", icon: HOST_KINDS[row.host_kind].icon, tone: "accent" }} meta={<>{HOST_KINDS[row.host_kind].label} · {row.vendor_name || "No vendor recorded"} · Purchased {formatDate(row.purchased_on)} · {row.warranty_expires_on ? <>Expires <RelativeTime date={row.warranty_expires_on} /></> : "No expiry recorded"}{row.serial_number ? ` · Serial: ${row.serial_number}` : ""}</>}
      right={<div className="flex flex-wrap items-center gap-3"><WarrantyStatusBadge status={row.status} /><span className="text-sm tabular-nums">{row.document_count} docs</span>
        {canManageRow(row) ? <button className="desk-button-ghost" onClick={() => setExpanded(`${row.host_kind}-${row.host_id}`)}>Manage</button> : null}</div>} />) }}
    pagination={{ page, pageSize: PAGE_SIZE, count: warranties.data?.count ?? 0, onChange: setPage }}
    detail={selected && canManageRow(selected) ? <DetailLayout presentation="drawer" open onClose={() => setExpanded(null)} title={selected.host_label} state={{ status: "ready" }}
      status={<WarrantyStatusBadge status={selected.status} />} main={<WarrantySection hostKind={selected.host_kind} hostId={selected.host_id} />} /> : null} />;
}
const HOST_KINDS: Record<WarrantyReportRow["host_kind"], { label: string; icon: IconName }> = {
 asset: { label: "Asset", icon: "Wrench" }, machine: { label: "Machine", icon: "Cog" }, printer: { label: "Printer", icon: "Printer" },
};
function formatDate(value: string | null) {
 if (!value) return "—";
 const date = new Date(value);
 return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
