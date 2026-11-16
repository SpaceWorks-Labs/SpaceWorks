import { formatDate as formatLibDate } from "../../../lib/format";
import { plural, t } from "@lingui/core/macro";
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
import { AreaOverviewPage } from "../areaOverview/AreaOverviewPage";

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
  const [params, setParams] = useSearchParams();
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
  const showView = (view: string) => setParams(current => { const next = new URLSearchParams(current); if (view) next.set("view", view); else next.delete("view"); return next; });
  // Decision 241: machines grouped by type, items by category, for each manager's own area.
  if (params.get("view") === "groups") return <AreaOverviewPage title={t`Warranties, grouped`} makerspaceId={makerspace.id} section="warranties" onBack={() => showView("")} />;
  return <ListLayout header={{ title: t`Warranties`, subtitle: t`Coverage for equipment you can manage in ${makerspace.name}.`, meta: plural(warranties.data?.count ?? 0, { one: "# item covered", other: "# items covered" }),
    overflow: [{ label: t`Group by area and machine type`, onClick: () => showView("groups") }] }}
    state={inventoryQueryState(warranties, "warranties")} isEmpty={!visibleRows.length} filtered={filtersActive}
    empty={{ message: t`No warranties recorded yet. Add one from a machine or asset.` }}
    filteredEmpty={{ message: t`Nothing matches these filters.`, action: { label: t`Clear filters`, onClick: () => list.restore({}) } }}
    tabs={["all", "active", "expiring_soon", "expired", "unknown"].map(key => ({ key, label: ({ all: t`All`, active: t`Active`, expiring_soon: t`Expiring soon`, expired: t`Expired`, unknown: t`Not covered` } as Record<string, string>)[key], href: href(key) }))} activeTab={status}
    filters={{ views: <button type="button" className={missingDocs ? "desk-button-primary" : "desk-button"} aria-pressed={missingDocs} onClick={() => list.setFilter("missing_docs", String(!missingDocs))}>{t`Missing docs`}</button>,
      controls: <Field label={t`Expires before`}><input className="desk-input" type="date" value={expiresBefore} onChange={event => list.setFilter("expires_before", event.target.value)} /></Field>,
      activeCount: expiresBefore ? 1 : 0,
      chips: expiresBefore ? [{ key: "expires_before", label: t`expires before ${expiresBefore}`, onRemove: () => list.setFilter("expires_before", "") }] : [] }}
    body={{ kind: "rows", rows: visibleRows.map(row => <ListRow key={`${row.host_kind}-${row.host_id}`} title={row.host_label}
      identity={{ kind: "icon", icon: hostKinds()[row.host_kind].icon, tone: "accent" }} meta={<>{hostKinds()[row.host_kind].label} · {row.vendor_name || t`No vendor recorded`} {t` · Purchased ${formatDate(row.purchased_on)} · `}{row.warranty_expires_on ? <>{t`Expires `}<RelativeTime date={row.warranty_expires_on} /></> : t`No expiry recorded`}{row.serial_number ? t` · Serial: ${row.serial_number}` : ""}</>}
      right={<div className="flex flex-wrap items-center gap-3"><WarrantyStatusBadge status={row.status} /><span className="text-sm tabular-nums">{plural(row.document_count, { one: "# doc", other: "# docs" })}</span>
        {canManageRow(row) ? <button className="desk-button-ghost" onClick={() => setExpanded(`${row.host_kind}-${row.host_id}`)}>{t`Manage`}</button> : null}</div>} />) }}
    pagination={{ page, pageSize: PAGE_SIZE, count: warranties.data?.count ?? 0, onChange: setPage }}
    detail={selected && canManageRow(selected) ? <DetailLayout presentation="drawer" open onClose={() => setExpanded(null)} title={selected.host_label} state={{ status: "ready" }}
      status={<WarrantyStatusBadge status={selected.status} />} main={<WarrantySection hostKind={selected.host_kind} hostId={selected.host_id} />} /> : null} />;
}
const hostKinds = (): Record<WarrantyReportRow["host_kind"], { label: string; icon: IconName }> => ({
 asset: { label: t`Asset`, icon: "Wrench" }, machine: { label: t`Machine`, icon: "Cog" }, printer: { label: t`Printer`, icon: "Printer" },
});
function formatDate(value: string | null) {
 if (!value) return "—";
 const date = new Date(value);
 return Number.isNaN(date.getTime()) ? "—" : formatLibDate(date, { year: "numeric", month: "short", day: "numeric" });
}
