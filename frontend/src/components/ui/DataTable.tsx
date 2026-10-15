import type { Key, ReactNode } from "react";
import { isValidElement, useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "./icon";
import { EmptyState } from "./EmptyState";
import { SkeletonRows } from "./Skeleton";
import { Spinner } from "./Spinner";
import { ListColumns } from "./ListColumns";
import type { UrlListState } from "../../lib/useUrlListState";

export type DataTableColumn<T> = {
  key: Extract<keyof T, string> | string; header: ReactNode; render?: (row: T) => ReactNode; sortable?: boolean; className?: string;
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
  emptyTitle = "No records",
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
    checked ? next.add(id) : next.delete(id);
    onSelectionChange?.([...next]);
  };
  const changeAll = (checked: boolean) => {
    const next = new Set(selectedSet);
    visibleIds.forEach((id) => (checked ? next.add(id) : next.delete(id)));
    onSelectionChange?.([...next]);
  };

  if (!loading && !data.length) return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;

  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-panel">
      {listState ? <ListColumns columns={columns} value={{ columns: listState.values.columns ?? "", density: listState.values.density ?? "comfortable" }} onChange={value => listState.restore({ ...listState.values, ...value })} /> : null}
      <table role="table" className="block w-full text-left text-sm md:table md:min-w-[640px]" aria-busy={loading}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead role="rowgroup" className="block bg-surface dark:bg-hover text-xs text-muted md:table-header-group">
          <tr role="row" className="flex flex-wrap items-center border-b border-line md:table-row">
            {selectionEnabled ? (
              <th role="columnheader" className="block w-16 px-3 py-2 md:table-cell" scope="col">
                <label className="inline-flex min-h-11 min-w-11 items-center justify-center"><input className="h-4 w-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" ref={selectAllRef} type="checkbox" aria-label="Select all rows" checked={allSelected} onChange={(event) => changeAll(event.target.checked)} /></label>
              </th>
            ) : null}
            {visibleColumns.map((column) => (
              <th role="columnheader"
                key={column.key}
                className={`block px-3 py-2 font-semibold md:table-cell ${column.className ?? ""}`}
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
                <tr role="row" key={id} className={`m-3 block min-w-0 rounded-xl border border-line md:m-0 md:table-row md:rounded-none md:border-x-0 md:border-t-0 md:last:border-b-0 ${selectedSet.has(id) ? "bg-accent-soft" : "hover:bg-hover"}`}>
                  {selectionEnabled ? (
                    <td role="cell" className="block px-3 py-2 md:table-cell">
                      <label className="inline-flex min-h-11 min-w-11 items-center justify-center"><input className="h-4 w-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox" aria-label={`Select row ${String(id)}`} checked={selectedSet.has(id)} onChange={(event) => changeRow(id, event.target.checked)} /></label>
                    </td>
                  ) : null}
                  {visibleColumns.map((column) => (
                    <td role="cell" key={column.key} className={`${cellPadding} block min-w-0 break-words text-ink md:table-cell ${column.key === "actions" ? "[&_button]:min-h-11 [&_button]:min-w-11 [&_a]:inline-flex [&_a]:min-h-11 [&_a]:min-w-11 [&_a]:items-center" : ""} ${column.className ?? ""}`}>
                      {/* Generated labels avoid duplicating cell text or controls during CSS reflow. */}
                      {columnLabels.get(column.key) ? <span aria-hidden="true" data-label={columnLabels.get(column.key)} className="mb-1 block text-xs text-muted before:content-[attr(data-label)] md:hidden" /> : null}
                      {column.render ? column.render(row) : String(getCellValue(row, column.key) ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
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
