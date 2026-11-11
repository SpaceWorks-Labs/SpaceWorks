import { t } from "@lingui/core/macro";
import { useContext, useEffect, useMemo, useState } from "react";

import { ListRow, StatusPill, RelativeTime, ErrorText } from "../../../components/ui";
import { downloadStaffFile } from "../../../lib/api";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import {
  formatDate,
  isOverdue,
  ledgerParams,
  UnitLines,
  sourceLabels,
  type LedgerResponse,
  type LedgerSourceFilter,
  type SortKey,
  type SortDirection,
} from "./LedgerParts";
import { ListLayout } from "../../../components/layouts";
import { ListSort } from "../../../components/layouts/ListSort";
import { useSearchParams } from "react-router-dom";
import { inventoryQueryState } from "./inventoryPresentation";
import { type Makerspace, useStaffGet } from "./shared";
import { useCrossLink } from "../crossLinks/staffHref";
import { RouteLink } from "../../../components/ui/RouteLink";
import { GROUPING_LABELS, LedgerGroupedRows, type LedgerGrouping } from "./LedgerGroups";
import type { LedgerRow } from "./LedgerParts";
import { MemberActivityDrawer } from "../memberActivity/MemberActivityDrawer";
import { StaffListContext } from "../StaffListContext";

const LEDGER_PAGE_SIZE = 50;

/** `canExport` is false for the handout desk: it reads the Ledger, but inventory-wide exports are refused (224(d)). */
export function Ledger({ makerspace, isSuperadmin, canExport = true }: { makerspace: Makerspace; isSuperadmin: boolean; canExport?: boolean }) {
  const [allMakerspaces, setAllMakerspaces] = useState(false);
  const [page, setPage] = useState(1);
  const [params, setParams] = useSearchParams();
  // `?q=` arrives from an item's lending history ("What they have out") and other cross-links.
  const [filter, setFilter] = useState(() => params.get("q") ?? "");
  const [grouping, setGrouping] = useState<LedgerGrouping>("");
  const link = useCrossLink();
  // A26: the borrower drawer (member 360) for reviewers; the handover desk is refused it by the server.
  const access = useContext(StaffListContext);
  const canSeeHistory = Boolean(isSuperadmin || access.actions?.some(action => ["view_inventory", "accept_request", "manage_members"].includes(action)));
  const openHistory = (userId: number) => setParams(current => { const next = new URLSearchParams(current); next.set("member", String(userId)); return next; });
  const sourceFilter = (params.get("source") ?? "") as LedgerSourceFilter;
  // The dashboard's overdue-loans tile links here with ?overdue=true (the lending area's own list).
  const [overdueOnly, setOverdueOnly] = useState(() => params.get("overdue") === "true");
  // The dashboard's due-today / due-soon tiles link here with ?due=today|soon.
  const dueParam = params.get("due");
  const dueWindow = dueParam === "today" || dueParam === "soon" ? dueParam : "";
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: "due",
    direction: "asc",
  });
  const debouncedFilter = useDebouncedValue(filter);
  const aggregate = isSuperadmin && allMakerspaces;
  const ledgerPath = aggregate ? "/admin/ledger" : `/admin/makerspace/${makerspace.id}/ledger`;
  const sortParam = `${sort.direction === "desc" ? "-" : ""}${sort.key}`;
  const ledgerQuery = useMemo(() => {
    const params = ledgerParams({
      page,
      pageSize: LEDGER_PAGE_SIZE,
      search: debouncedFilter,
      source: sourceFilter,
      overdueOnly,
      due: dueWindow,
      sort: sortParam,
    });
    return params.toString();
  }, [debouncedFilter, dueWindow, overdueOnly, page, sortParam, sourceFilter]);
  const exportQuery = useMemo(() => {
    const params = ledgerParams({
      search: debouncedFilter,
      source: sourceFilter,
      overdueOnly,
      due: dueWindow,
      sort: sortParam,
    });
    return params.toString();
  }, [debouncedFilter, dueWindow, overdueOnly, sortParam, sourceFilter]);
  const ledger = useStaffGet<LedgerResponse>(
    ["ledger", aggregate ? "all" : makerspace.id, ledgerQuery],
    `${ledgerPath}?${ledgerQuery}`,
  );

  useEffect(() => {
    setPage(1);
  }, [aggregate, debouncedFilter, dueWindow, makerspace.id, overdueOnly, sort.direction, sort.key, sourceFilter]);

  const rows = ledger.data?.results ?? [];
  const now = Date.now();
  const itemCount = rows.reduce((total, row) => total + row.quantity, 0);
  const totalRows = ledger.data?.count ?? 0;
  const [exportError, setExportError] = useState("");

  const setSortKey = (key: SortKey) => {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === "asc" ? "desc" : "asc",
    }));
  };

  const exportLedger = (format: "csv" | "xlsx") => {
    const params = new URLSearchParams(exportQuery);
    params.set("format", format);
    const filename = aggregate ? `ledger-all.${format}` : `ledger-${makerspace.slug}.${format}`;
    setExportError("");
    void downloadStaffFile(`${ledgerPath}/export?${params.toString()}`, filename).catch(() => setExportError(t`Couldn’t export the ledger. Try again.`));
  };

  // IN7: a row opens its loan; the item and the holder's other loans are one click away.
  const renderRow = (row: LedgerRow, index: number) => {
    const itemHref = !aggregate && row.product_id ? link("inventory", { item: row.product_id }) : undefined;
    return <ListRow key={`${row.source}-${row.reference_id}-${index}`} title={`${row.item_name} ×${row.quantity}`}
      identity={{ kind: "avatar", name: row.holder, seed: row.holder }}
      href={!aggregate && row.request_id ? link("requests", { id: row.request_id }) : undefined}
      meta={<>{row.holder} · {row.container ? t`Box: ${row.container} · ` : ""}{t`${sourceLabels[row.source]} · Out since `}{row.since ? <RelativeTime date={row.since} exact /> : "unknown"}<UnitLines row={row} />{aggregate ? t` · Makerspace ${row.makerspace_id}` : null}</>}
      right={<span className="flex flex-wrap items-center justify-end gap-2">
        <StatusPill tone={isOverdue(row.due, now) ? "danger" : "neutral"} label={isOverdue(row.due, now) ? t`Overdue ${Math.max(1, Math.ceil((now - new Date(row.due!).getTime()) / 86400000))} days` : row.due ? t`Due ${formatDate(row.due)}` : t`No due date`} />
        {itemHref ? <RouteLink className="text-sm font-semibold underline" href={itemHref}>{t`Item`}</RouteLink> : null}
        {!aggregate && canSeeHistory && row.holder_id ? <button type="button" className="desk-button-ghost text-sm" onClick={() => openHistory(row.holder_id!)}>{t`Borrower history`}</button> : null}
        {filter !== row.holder ? <button type="button" className="desk-button-ghost text-sm" onClick={() => setFilter(row.holder)}>{t`All from ${row.holder}`}</button> : null}
      </span>} />;
  };

  const tabHref = (value: string) => { const next = new URLSearchParams(params); next.set("source", value); return `?${next}`; };
  return <ListLayout header={{ title: t`Ledger`, subtitle: t`Everything that's out right now.`, meta: aggregate ? "Across all makerspaces" : makerspace.name,
    secondary: isSuperadmin ? { label: aggregate ? t`This makerspace only` : t`All makerspaces`, icon: "Building2", onClick: () => { if (aggregate && sort.key === "makerspace_id") setSort({ key: "due", direction: "asc" }); setAllMakerspaces(value => !value); } } : undefined,
    overflow: canExport ? [{ label: t`Export CSV`, onClick: () => exportLedger("csv") }, { label: t`Export Excel`, onClick: () => exportLedger("xlsx") }] : [] }}
    state={inventoryQueryState(ledger, "the ledger")} isEmpty={!rows.length} filtered={Boolean(filter || overdueOnly || sourceFilter || dueWindow)}
    empty={{ message: t`Nothing is out right now. Loans appear here the moment they're handed over.` }}
    filteredEmpty={{ message: t`Nothing matches these filters.`, action: { label: t`Clear filters`, onClick: () => { setFilter(""); setOverdueOnly(false); setParams(current => { current.delete("source"); current.delete("due"); return current; }); } } }}
    stats={[{ label: t`Items out on this page`, value: itemCount }, { label: t`Records`, value: totalRows }]}
    tabs={[{ key: "", label: t`All`, href: tabHref("") }, { key: "reviewed", label: t`Reviewed`, href: tabHref("reviewed") }, { key: "self_checkout", label: t`Self-checkout`, href: tabHref("self_checkout") }, { key: "direct", label: t`Direct`, href: tabHref("direct") }]} activeTab={sourceFilter}
    filters={{ search: { label: t`Search ledger`, value: filter, onChange: setFilter },
      sort: <div className="flex min-w-0 flex-wrap items-center gap-2">
        <ListSort label={t`Sort ledger`} value={sort.key} onChange={event => setSortKey(event.target.value as SortKey)} options={sortOptions(aggregate)} />
        <button type="button" className="desk-button" onClick={() => setSort(current => ({ ...current, direction: current.direction === "asc" ? "desc" : "asc" }))}>{sort.direction === "asc" ? t`Ascending` : t`Descending`}</button>
        {!aggregate ? <label className="flex min-w-0 items-center gap-2 text-sm">{t`Group`}
          <select className="desk-input max-w-full" value={grouping} onChange={event => setGrouping(event.target.value as LedgerGrouping)}>
            {(Object.keys(GROUPING_LABELS) as LedgerGrouping[]).map(key => <option key={key} value={key}>{GROUPING_LABELS[key]}</option>)}
          </select></label> : null}
      </div>,
      views: <span className="flex flex-wrap items-center gap-2"><label className="flex items-center gap-2 text-sm">{t`Due`}
        <select className="desk-input" value={dueWindow} onChange={event => setParams(current => { const next = new URLSearchParams(current); if (event.target.value) next.set("due", event.target.value); else next.delete("due"); return next; }, { replace: true })}>
          <option value="">{t`Any time`}</option><option value="today">{t`Due today`}</option><option value="soon">{t`Due soon`}</option></select></label><button type="button" className={overdueOnly ? "desk-button-primary" : "desk-button"} aria-pressed={overdueOnly} onClick={() => setOverdueOnly(value => !value)}>{t`Overdue only`}</button></span> }}
    body={{ kind: "rows", rows: grouping && !aggregate ? <LedgerGroupedRows rows={rows} grouping={grouping} renderRow={renderRow} /> : rows.map(renderRow) }}
    pagination={{ page, pageSize: LEDGER_PAGE_SIZE, count: totalRows, onChange: setPage }} detail={<><ErrorText message={exportError} />{!aggregate && canSeeHistory ? <MemberActivityDrawer makerspaceId={makerspace.id} title={t`Borrower history`} /> : null}</>} />;
}

const SORT_LABELS: Record<SortKey, string> = { item_name: t`Item`, holder: t`Holder`, quantity: t`Quantity`, since: t`Out since`, due: t`Due date`, source: t`Source`, makerspace_id: t`Makerspace` };
function sortOptions(aggregate: boolean) {
  return (Object.keys(SORT_LABELS) as SortKey[]).filter(key => aggregate || key !== "makerspace_id").map(key => [key, SORT_LABELS[key]] as const);
}
