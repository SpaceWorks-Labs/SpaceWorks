import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";

export type LedgerSource = "request" | "self_checkout" | "direct_handout";
export type LedgerSourceFilter = "" | "reviewed" | "self_checkout" | "direct";

export type LedgerRow = {
  source: LedgerSource;
  item_name: string;
  container: string | null;
  units: Array<{ asset_tag: string; serial_number: string }>;
  target_label: string | null;
  holder: string;
  quantity: number;
  since: string | null;
  due: string | null;
  makerspace_id: number;
  reference_id: number;
  status: string;
  /** Drill-down keys (IN7); absent on servers older than 0.12.0. */
  request_id?: number | null;
  product_id?: number | null;
  holder_id?: number | null;
};

export type LedgerResponse = {
  count: number;
  results: LedgerRow[];
};

export type SortKey = "item_name" | "holder" | "quantity" | "since" | "due" | "source" | "makerspace_id";
export type SortDirection = "asc" | "desc";

export const sourceLabels: Record<LedgerSource, string> = {
  request: t`Request`,
  self_checkout: t`Self-checkout`,
  direct_handout: t`Direct`,
};

export function UnitLines({ row }: { row: LedgerRow }) {
  if (row.units.length) {
    return (
      <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-xs text-muted">
        {row.units.map((unit) => (
          <span className="break-words" key={`${unit.asset_tag}-${unit.serial_number || "no-serial"}`}>
            #{unit.asset_tag}
            {unit.serial_number ? ` - ${unit.serial_number}` : ""}
          </span>
        ))}
      </div>
    );
  }

  return row.target_label ? <div className="mt-0.5 break-words text-xs text-muted">{row.target_label}</div> : null;
}

export function SortableHeader({
  label,
  sortKey,
  sort,
  onSort,
  align = "left",
}: {
  label: string;
  sortKey: SortKey;
  sort: { key: SortKey; direction: SortDirection };
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
}) {
  const active = sort.key === sortKey;
  return (
    <th scope="col" className={`whitespace-nowrap px-3 py-2 ${align === "right" ? "text-right" : "text-left"}`}>
      <button
        type="button"
        className={`desk-button-ghost ${align === "right" ? "justify-end" : ""}`}
        onClick={() => onSort(sortKey)}
      >
        {label}
        <span className="text-[10px]">{active ? (sort.direction === "asc" ? "^" : "v") : "-"}</span>
      </button>
    </th>
  );
}

export function ledgerParams({
  page,
  pageSize,
  search,
  source,
  overdueOnly,
  due = "",
  sort,
}: {
  page?: number;
  pageSize?: number;
  search: string;
  source: LedgerSourceFilter;
  overdueOnly: boolean;
  /** The dashboard's due-back windows: `today` or `soon` (the next three days). */
  due?: string;
  sort: string;
}) {
  const params = new URLSearchParams();
  if (page) params.set("page", String(page));
  if (pageSize) params.set("page_size", String(pageSize));
  const trimmed = search.trim();
  if (trimmed) params.set("search", trimmed);
  if (source) params.set("source", source);
  if (overdueOnly) params.set("overdue", "true");
  if (due) params.set("due", due);
  params.set("sort", sort);
  return params;
}

export function isOverdue(value: string | null, now: number) {
  return Boolean(value && new Date(value).getTime() < now);
}

export function formatDate(value: string | null) {
  if (!value) return "\u2014";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "\u2014";
  return date.toLocaleDateString(formatLocale(), { year: "numeric", month: "short", day: "numeric" });
}
