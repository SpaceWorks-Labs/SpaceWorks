import { t } from "@lingui/core/macro";
import type { Key, ReactNode } from "react";
import { isValidElement, useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "./icon";
import { EmptyState } from "./EmptyState";
import { SkeletonRows } from "./Skeleton";
import { Spinner } from "./Spinner";
import { ListColumns } from "./ListColumns";
import type { UrlListState } from "../../lib/useUrlListState";

/** Where a cell sits in the stacked phone card: a small grid with the selection box and `lead` (a thumbnail)
 * on the left, the `title` with its `status` directly under it on the right, then one "Label value" line per
 * `detail` cell and the actions last. `hidden` cells are tablet+ only. Defaults: the first column is the title,
 * a `status` key is the status, `actions` sit at the bottom, everything else is a detail. */
export type PhoneRole = "lead" | "title" | "status" | "detail" | "hidden";
export type DataTableColumn<T> = {
  key: Extract<keyof T, string> | string; header: ReactNode; render?: (row: T) => ReactNode; sortable?: boolean; className?: string;
  phone?: PhoneRole;
};
const PHONE_CELL: Record<PhoneRole | "actions" | "select", string> = {
  select: "max-md:col-start-1 max-md:row-span-2 max-md:row-start-1 max-md:mr-2 max-md:self-center max-md:p-0",
  lead: "max-md:col-start-2 max-md:row-span-2 max-md:row-start-1 max-md:mr-3 max-md:self-center max-md:p-0",
  title: "max-md:col-start-3 max-md:row-start-1 max-md:self-end max-md:p-0 max-md:font-semibold",
  status: "max-md:col-start-3 max-md:row-start-2 max-md:self-start max-md:p-0",
  detail: "max-md:col-span-full max-md:flex max-md:items-baseline max-md:gap-2 max-md:p-0 max-md:pt-1",
  hidden: "max-md:hidden",
  actions: "max-md:col-span-full max-md:mt-2 max-md:border-t max-md:border-line max-md:p-0 max-md:pt-2",
};

type SortState = { key: string; direction: "asc" | "desc" };

export type DataTableProps<T> = {
  columns: DataTableColumn<T>[]; data: T[]; getRowId?: (row: T) => Key; selectedIds?: Key[];
  onSelectionChange?: (ids: Key[]) => void; loading?: boolean; emptyTitle?: string; emptyDescription?: string; emptyAction?: ReactNode;
  skeletonCols?: number;
  ordering?: string; onOrderingChange?: (ordering: string) => void;
  listState?: UrlListState;
  /** Optional screen-reader caption naming the table. */
  caption?: string;
};

export function DataTable<T>({
  columns,
  data,
  getRowId = defaultGetRowId,
  selectedIds,
  onSelectionChange,
  loading = false,
  emptyTitle = t`No records`,
  emptyDescription,
  emptyAction,
  skeletonCols,
  ordering, onOrderingChange, listState, caption,
}: DataTableProps<T>) {
  const [localSort, setSort] = useState<SortState | null>(null);
  const sort: SortState | null = ordering !== undefined ? { key: ordering.replace(/^-/, ""), direction: ordering.startsWith("-") ? "desc" : "asc" } : localSort;
  const selectedSet = useMemo(() => new Set(selectedIds ?? []), [selectedIds]);
  const visibleIds = useMemo(() => data.map(getRowId), [data, getRowId]);
  const selectionEnabled = Boolean(selectedIds && onSelectionChange);
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedSet.has(id));
  const someSelected = visibleIds.some((id) => selectedSet.has(id));
  const selectAllRef = useRef<HTMLInputElement>(null);
  const chosen = listState?.values.columns?.split(",") ?? [];
  const filtered = columns.filter(column => chosen.includes(column.key));
  const visibleColumns = filtered.length ? filtered : columns;
  const columnLabels = new Map(visibleColumns.map(column => [column.key, headerText(column.header)]));
  const cellPadding = listState?.values.density === "compact" ? "px-3 py-1" : "px-3 py-2";
  // Phones read rows as stacked cards: only interactive headers (sort, select all) stay visible.
  // When the page drives ordering (its toolbar has a Sort select), sort chips would repeat it on phones.
  const phoneSortChips = ordering === undefined && visibleColumns.some(column => column.sortable);
  const phoneHeader = selectionEnabled || phoneSortChips;
  const phoneRole = (column: DataTableColumn<T>, index: number): PhoneRole | "actions" =>
    column.key === "actions" ? "actions" : column.phone ?? (column.key === "status" ? "status" : index === 0 ? "title" : "detail");

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someSelected && !allSelected;
  }, [allSelected, someSelected]);

  const sortedData = useMemo(() => {
    if (!sort || ordering !== undefined) return data;
    return [...data].sort((a, b) => compareValues(getCellValue(a, sort.key), getCellValue(b, sort.key), sort.direction));
  }, [data, sort, ordering]);

  const toggleSort = (column: DataTableColumn<T>) => {
    if (!column.sortable) return;
    if (onOrderingChange) { onOrderingChange(sort?.key === column.key && sort.direction === "asc" ? `-${column.key}` : column.key); return; }
    setSort((current) => ({
      key: column.key,
      direction: current?.key === column.key && current.direction === "asc" ? "desc" : "asc",
    }));
  };
  const changeRow = (id: Key, checked: boolean) => {
    const next = new Set(selectedSet);
    if (checked) next.add(id); else next.delete(id);
    onSelectionChange?.([...next]);
  };
  const changeAll = (checked: boolean) => {
    const next = new Set(selectedSet);
    visibleIds.forEach((id) => (checked ? next.add(id) : next.delete(id)));
    onSelectionChange?.([...next]);
  };

  if (!loading && !data.length) return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;

  return (
    <div className="min-w-0 rounded-xl border border-line bg-panel">
      {listState ? <ListColumns columns={columns} value={{ columns: listState.values.columns ?? "", density: listState.values.density ?? "comfortable" }} onChange={value => listState.restore({ ...listState.values, ...value })} /> : null}
      {/* Tablet+: wide tables scroll inside this box, never the page. */}
      <div role="region" aria-label={caption || t`Table data`} tabIndex={0} className="overflow-x-auto overscroll-x-contain rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <table role="table" className="block w-full text-left text-sm md:table md:min-w-[640px]" aria-busy={loading}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead role="rowgroup" className={`${phoneHeader ? "block" : "max-md:sr-only"} bg-surface dark:bg-hover text-xs text-muted md:table-header-group`}>
          <tr role="row" className="flex flex-wrap items-center border-b border-line md:table-row">
            {selectionEnabled ? (
              <th role="columnheader" className="block w-16 px-3 py-2 md:table-cell" scope="col">
                <label className="inline-flex min-h-11 min-w-11 items-center justify-center"><input className="h-4 w-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" ref={selectAllRef} type="checkbox" aria-label={t`Select all rows`} checked={allSelected} onChange={(event) => changeAll(event.target.checked)} /></label>
              </th>
            ) : null}
            {visibleColumns.map((column) => (
              <th role="columnheader"
                key={column.key}
                className={`${column.sortable && phoneSortChips ? "block" : "max-md:sr-only"} px-3 py-2 font-semibold md:table-cell ${column.className ?? ""}`}
                aria-sort={sort?.key === column.key ? ariaSort(sort.direction) : undefined}
                scope="col"
              >
                {column.sortable ? (
                  <button type="button" aria-label={columnLabels.get(column.key) ? undefined : column.key} className="inline-flex min-h-11 min-w-11 items-center gap-1 rounded-control font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" onClick={() => toggleSort(column)}>
                    {column.header}
                    <Icon name={sort?.key === column.key ? sort.direction === "asc" ? "ArrowUp" : "ArrowDown" : "ArrowUpDown"} className="h-4 w-4" />
                  </button>
                ) : column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup" className="block md:table-row-group">
          {loading && skeletonCols ? (
            <SkeletonRows rows={6} cols={listState ? visibleColumns.length + (selectionEnabled ? 1 : 0) : skeletonCols} />
          ) : loading ? (
            <tr role="row" className="block md:table-row">
              <td role="cell" className="block px-3 py-8 text-center md:table-cell" colSpan={visibleColumns.length + (selectionEnabled ? 1 : 0)}>
                <Spinner />
              </td>
            </tr>
          ) : (
            sortedData.map((row) => {
              const id = getRowId(row);
              return (
                <tr role="row" key={id} className={`m-3 block min-w-0 max-md:grid max-md:grid-cols-[auto_auto_minmax(0,1fr)] max-md:gap-y-1 max-md:p-3 rounded-xl border border-line md:m-0 md:table-row md:rounded-none md:border-x-0 md:border-t-0 md:last:border-b-0 ${selectedSet.has(id) ? "bg-accent-soft" : "hover:bg-hover"}`}>
                  {selectionEnabled ? (
                    <td role="cell" className={`block px-3 py-2 md:table-cell ${PHONE_CELL.select}`}>
                      <label className="inline-flex min-h-11 min-w-11 items-center justify-center"><input className="h-4 w-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox" aria-label={t`Select row ${String(id)}`} checked={selectedSet.has(id)} onChange={(event) => changeRow(id, event.target.checked)} /></label>
                    </td>
                  ) : null}
                  {visibleColumns.map((column, index) => {
                    const role = phoneRole(column, index);
                    const label = role === "detail" ? columnLabels.get(column.key) : undefined;
                    const place = PHONE_CELL[role];
                    return <td role="cell" key={column.key} className={`${cellPadding} block min-w-0 break-words text-ink md:table-cell ${place} ${role === "actions" ? "[&_button]:min-h-11 [&_button]:min-w-11 [&_a]:inline-flex [&_a]:min-h-11 [&_a]:min-w-11 [&_a]:items-center" : ""} ${column.className ?? ""}`}>
                      {/* Generated labels avoid duplicating cell text or controls during CSS reflow; only detail cells carry one. */}
                      {label ? <span aria-hidden="true" data-label={label} className="shrink-0 text-xs text-muted before:content-[attr(data-label)] md:hidden" /> : null}
                      {column.render ? column.render(row) : String(getCellValue(row, column.key) ?? "")}
                    </td>;
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function defaultGetRowId<T>(row: T): Key {
  return (row as { id: Key }).id;
}

function getCellValue<T>(row: T, key: string) {
  return (row as Record<string, unknown>)[key];
}

function ariaSort(direction: "asc" | "desc") {
  return direction === "asc" ? "ascending" : "descending";
}

function compareValues(left: unknown, right: unknown, direction: "asc" | "desc") {
  const order = direction === "asc" ? 1 : -1;
  if (left == null && right == null) return 0;
  if (left == null) return -1 * order;
  if (right == null) return 1 * order;
  if (typeof left === "number" && typeof right === "number") return (left - right) * order;
  return String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: "base" }) * order;
}

function headerText(header: ReactNode): string {
  if (typeof header === "string" || typeof header === "number") return String(header);
  if (Array.isArray(header)) return header.map(headerText).join("");
  if (isValidElement<{ children?: ReactNode }>(header)) return headerText(header.props.children);
  return "";
}
