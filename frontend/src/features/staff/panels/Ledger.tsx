import { useEffect, useMemo, useState } from "react";

import { Field, ListRow, StatusPill, RelativeTime, ErrorText } from "../../../components/ui";
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
    void downloadStaffFile(`${ledgerPath}/export?${params.toString()}`, filename).catch(() => setExportError("Couldn’t export the ledger. Try again."));
  };

  const tabHref = (value: string) => { const next = new URLSearchParams(params); next.set("source", value); return `?${next}`; };
  return <ListLayout header={{ title: "Ledger", subtitle: "Everything that's out right now.", meta: aggregate ? "Across all makerspaces" : makerspace.name,
    overflow: [{ label: "Export CSV", onClick: () => exportLedger("csv") }, { label: "Export Excel", onClick: () => exportLedger("xlsx") }] }}
    state={inventoryQueryState(ledger, "the ledger")} isEmpty={!rows.length} filtered={Boolean(filter || overdueOnly || sourceFilter)}
    empty={{ message: "Nothing is out right now. Loans appear here the moment they're handed over." }}
    filteredEmpty={{ message: "Nothing matches these filters.", action: { label: "Clear filters", onClick: () => { setFilter(""); setOverdueOnly(false); setParams(current => { current.delete("source"); return current; }); } } }}
    stats={[{ label: "Items out on this page", value: itemCount }, { label: "Records", value: totalRows }]}
    tabs={[{ key: "", label: "All", href: tabHref("") }, { key: "reviewed", label: "Reviewed", href: tabHref("reviewed") }, { key: "self_checkout", label: "Self-checkout", href: tabHref("self_checkout") }, { key: "direct", label: "Direct", href: tabHref("direct") }]} activeTab={sourceFilter}
    filters={{ search: { label: "Search ledger", value: filter, onChange: setFilter }, controls: <>
      <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={overdueOnly} onChange={event => setOverdueOnly(event.target.checked)} />Overdue</label>
      {isSuperadmin ? <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={allMakerspaces} onChange={event => setAllMakerspaces(event.target.checked)} />All makerspaces</label> : null}
      <Field label="Sort ledger"><select className="desk-input" value={sort.key} onChange={event => setSortKey(event.target.value as SortKey)}>{["item_name", "holder", "quantity", "since", "due", "source", ...(aggregate ? ["makerspace_id"] : [])].map(key => <option key={key} value={key}>{key.replace(/_/g, " ")}</option>)}</select></Field>
      <button className="desk-button" onClick={() => setSort(current => ({ ...current, direction: current.direction === "asc" ? "desc" : "asc" }))}>{sort.direction === "asc" ? "Ascending" : "Descending"}</button>
    </> }}
    body={{ kind: "rows", rows: rows.map((row, index) => <ListRow key={`${row.source}-${row.reference_id}-${index}`} title={`${row.item_name} ×${row.quantity}`}
      identity={{ kind: "avatar", name: row.holder, seed: row.holder }}
      meta={<>{row.holder} · {row.container ? `Box: ${row.container} · ` : ""}{sourceLabels[row.source]} · Out since {row.since ? <RelativeTime date={row.since} /> : "unknown"}<UnitLines row={row} />{aggregate ? ` · Makerspace ${row.makerspace_id}` : null}</>}
      right={<StatusPill tone={isOverdue(row.due, now) ? "danger" : "neutral"} label={isOverdue(row.due, now) ? `Overdue ${Math.max(1, Math.ceil((now - new Date(row.due!).getTime()) / 86400000))} days` : row.due ? `Due ${formatDate(row.due)}` : "No due date"} />} />) }}
    pagination={{ page, pageSize: LEDGER_PAGE_SIZE, count: totalRows, onChange: setPage }} detail={<ErrorText message={exportError} />} />;
}
