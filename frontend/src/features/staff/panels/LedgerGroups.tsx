import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

import type { LedgerRow } from "./LedgerParts";

export type LedgerGrouping = "" | "holder" | "item";

export const GROUPING_LABELS: Record<LedgerGrouping, string> = { "": t`No grouping`, holder: t`Group by holder`, item: t`Group by item` };

/**
 * IN7: the ledger page grouped by who holds it or by what is out. Groups are built from the
 * rows already on screen (the server pages and sorts), each with its own item total, so a
 * holder with five loans reads as one block instead of five scattered rows.
 */
export function groupLedgerRows(rows: LedgerRow[], grouping: LedgerGrouping) {
  const groups = new Map<string, { label: string; quantity: number; rows: LedgerRow[] }>();
  for (const row of rows) {
    const key = grouping === "holder" ? `h:${row.holder_id ?? row.holder}` : `i:${row.product_id ?? row.item_name}`;
    const group = groups.get(key) ?? { label: grouping === "holder" ? row.holder : row.item_name, quantity: 0, rows: [] };
    group.quantity += row.quantity;
    group.rows.push(row);
    groups.set(key, group);
  }
  return [...groups.entries()].map(([key, group]) => ({ key, ...group }));
}

export function LedgerGroupedRows({ rows, grouping, renderRow }: {
  rows: LedgerRow[]; grouping: Exclude<LedgerGrouping, "">; renderRow: (row: LedgerRow, index: number) => ReactNode;
}) {
  return <div className="grid min-w-0 gap-4">{groupLedgerRows(rows, grouping).map(group =>
    <section key={group.key} className="grid min-w-0 gap-2" aria-label={group.label}>
      <h3 className="flex flex-wrap items-baseline justify-between gap-2 title-section">
        <span className="[overflow-wrap:anywhere]">{group.label}</span>
        <span className="text-sm font-normal text-muted">{t`${group.rows.length} records · ${group.quantity} items out`}</span>
      </h3>
      {group.rows.map(renderRow)}
    </section>)}
  </div>;
}
