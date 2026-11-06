import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";

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

const LEDGER_PAGE_SIZE = 50;

export function Ledger({ makerspace, isSuperadmin }: { makerspace: Makerspace; isSuperadmin: boolean }) {
  const [allMakerspaces, setAllMakerspaces] = useState(false);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [params, setParams] = useSearchParams();
  const sourceFilter = (params.get("source") ?? "") as LedgerSourceFilter;
  const [overdueOnly, setOverdueOnly] = useState(false);
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
      sort: sortParam,
    });
    return params.toString();
  }, [debouncedFilter, overdueOnly, page, sortParam, sourceFilter]);
  const exportQuery = useMemo(() => {
    const params = ledgerParams({
      search: debouncedFilter,
      source: sourceFilter,
      overdueOnly,
      sort: sortParam,
    });
    return params.toString();
  }, [debouncedFilter, overdueOnly, sortParam, sourceFilter]);
  const ledger = useStaffGet<LedgerResponse>(
    ["ledger", aggregate ? "all" : makerspace.id, ledgerQuery],
    `${ledgerPath}?${ledgerQuery}`,
  );

  useEffect(() => {
    setPage(1);
  }, [aggregate, debouncedFilter, makerspace.id, overdueOnly, sort.direction, sort.key, sourceFilter]);

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

  const tabHref = (value: string) => { const next = new URLSearchParams(params); next.set("source", value); return `?${next}`; };
  return <ListLayout header={{ title: t`Ledger`, subtitle: t`Everything that's out right now.`, meta: aggregate ? "Across all makerspaces" : makerspace.name,
    secondary: isSuperadmin ? { label: aggregate ? t`This makerspace only` : t`All makerspaces`, icon: "Building2", onClick: () => { if (aggregate && sort.key === "makerspace_id") setSort({ key: "due", direction: "asc" }); setAllMakerspaces(value => !value); } } : undefined,
    overflow: [{ label: t`Export CSV`, onClick: () => exportLedger("csv") }, { label: t`Export Excel`, onClick: () => exportLedger("xlsx") }] }}
    state={inventoryQueryState(ledger, "the ledger")} isEmpty={!rows.length} filtered={Boolean(filter || overdueOnly || sourceFilter)}
    empty={{ message: t`Nothing is out right now. Loans appear here the moment they're handed over.` }}
    filteredEmpty={{ message: t`Nothing matches these filters.`, action: { label: t`Clear filters`, onClick: () => { setFilter(""); setOverdueOnly(false); setParams(current => { current.delete("source"); return current; }); } } }}
    stats={[{ label: t`Items out on this page`, value: itemCount }, { label: t`Records`, value: totalRows }]}
    tabs={[{ key: "", label: t`All`, href: tabHref("") }, { key: "reviewed", label: t`Reviewed`, href: tabHref("reviewed") }, { key: "self_checkout", label: t`Self-checkout`, href: tabHref("self_checkout") }, { key: "direct", label: t`Direct`, href: tabHref("direct") }]} activeTab={sourceFilter}
    filters={{ search: { label: t`Search ledger`, value: filter, onChange: setFilter },
      sort: <div className="flex min-w-0 flex-wrap items-center gap-2">
        <ListSort label={t`Sort ledger`} value={sort.key} onChange={event => setSortKey(event.target.value as SortKey)} options={sortOptions(aggregate)} />
        <button type="button" className="desk-button" onClick={() => setSort(current => ({ ...current, direction: current.direction === "asc" ? "desc" : "asc" }))}>{sort.direction === "asc" ? t`Ascending` : t`Descending`}</button>
      </div>,
      views: <button type="button" className={overdueOnly ? "desk-button-primary" : "desk-button"} aria-pressed={overdueOnly} onClick={() => setOverdueOnly(value => !value)}>{t`Overdue only`}</button> }}
    body={{ kind: "rows", rows: rows.map((row, index) => <ListRow key={`${row.source}-${row.reference_id}-${index}`} title={`${row.item_name} ×${row.quantity}`}
      identity={{ kind: "avatar", name: row.holder, seed: row.holder }}
      meta={<>{row.holder} · {row.container ? t`Box: ${row.container} · ` : ""}{t`${sourceLabels[row.source]} · Out since `}{row.since ? <RelativeTime date={row.since} exact /> : "unknown"}<UnitLines row={row} />{aggregate ? t` · Makerspace ${row.makerspace_id}` : null}</>}
      right={<StatusPill tone={isOverdue(row.due, now) ? "danger" : "neutral"} label={isOverdue(row.due, now) ? t`Overdue ${Math.max(1, Math.ceil((now - new Date(row.due!).getTime()) / 86400000))} days` : row.due ? t`Due ${formatDate(row.due)}` : t`No due date`} />} />) }}
    pagination={{ page, pageSize: LEDGER_PAGE_SIZE, count: totalRows, onChange: setPage }} detail={<ErrorText message={exportError} />} />;
}

const SORT_LABELS: Record<SortKey, string> = { item_name: t`Item`, holder: t`Holder`, quantity: t`Quantity`, since: t`Out since`, due: t`Due date`, source: t`Source`, makerspace_id: t`Makerspace` };
function sortOptions(aggregate: boolean) {
  return (Object.keys(SORT_LABELS) as SortKey[]).filter(key => aggregate || key !== "makerspace_id").map(key => [key, SORT_LABELS[key]] as const);
}
