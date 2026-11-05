import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusPill } from "../../../components/ui";
import type { ShopAccess } from "./shopAccess";
import { ShopMovements } from "./ShopMovements";
import { ShopStockDialog, type StockTarget } from "./ShopStockDialog";
import { listAllProducts, moveStock, staffShopError, staffShopKeys, type StockMove } from "./staffShopApi";

type Row = StockTarget & { held: number; available: number; reorder: number; sku: string };

/** Stock per variant: on hand, held for orders, available, and the reorder point. Managers restock and adjust. */
export function ShopStock({ makerspaceId, access }: { makerspaceId: number; access: ShopAccess }) {
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<{ target: StockTarget; mode: "restock" | "adjust" } | null>(null);
  const [history, setHistory] = useState<StockTarget | null>(null);
  const query = useQuery({ queryKey: staffShopKeys.allProducts(makerspaceId), queryFn: () => listAllProducts(makerspaceId) });
  const rows = useMemo<Row[]>(() => (query.data ?? []).flatMap(product => (product.variants ?? []).filter(variant => variant.id && !variant.archived_at)
    .map(variant => ({ variantId: variant.id as number, onHand: variant.on_hand, held: variant.held, available: variant.available,
      reorder: variant.reorder_point ?? 0, sku: variant.sku ?? "",
      label: (product.variants?.length ?? 0) > 1 ? `${product.name} · ${variant.name}` : product.name }))), [query.data]);
  const term = search.trim().toLowerCase();
  const shown = term ? rows.filter(row => row.label.toLowerCase().includes(term) || row.sku.toLowerCase().includes(term)) : rows;
  const move = useMutation({ mutationFn: ({ id, body }: { id: number; body: StockMove }) => moveStock(id, body),
    onSuccess: () => { setDialog(null); void client.invalidateQueries({ queryKey: staffShopKeys.all(makerspaceId) }); } });
  return <>
    <ListLayout header={{ eyebrow: "Shop", title: "Stock", subtitle: "Held stock is set aside for orders that are not collected yet." }}
      state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: staffShopError(query.error),
        onRetry: () => { void query.refetch(); } } : { status: "ready" }}
      filters={{ search: { label: "Find an item", placeholder: "Name or SKU", value: search, onChange: setSearch } }}
      isEmpty={!shown.length} empty={{ message: "No products to stock yet." }} filteredEmpty={{ message: "No item matches." }}
      body={{ kind: "rows", rows: shown.map(row => {
        const low = row.reorder > 0 && row.available <= row.reorder;
        return <ListRow key={row.variantId} title={row.label}
          meta={<span className="text-sm tabular-nums text-muted">{row.sku ? `${row.sku} · ` : ""}{row.onHand} on hand · {row.held} held · {row.available} available{row.reorder ? ` · reorder at ${row.reorder}` : ""}</span>}
          right={<span className="flex flex-wrap items-center gap-2">
            {row.available <= 0 ? <StatusPill label="Sold out" tone="danger" /> : low ? <StatusPill label="Low" tone="warn" /> : null}
            <button type="button" className="desk-button min-h-11" aria-label={`Stock history for ${row.label}`} onClick={() => setHistory(row)}>History</button>
            {access.manage ? <>
              <button type="button" className="desk-button min-h-11" aria-label={`Restock ${row.label}`} onClick={() => { move.reset(); setDialog({ target: row, mode: "restock" }); }}>Restock</button>
              <button type="button" className="desk-button min-h-11" aria-label={`Adjust ${row.label}`} onClick={() => { move.reset(); setDialog({ target: row, mode: "adjust" }); }}>Adjust</button>
            </> : null}
          </span>} />;
      }) }} />
    {dialog ? <ShopStockDialog target={dialog.target} mode={dialog.mode} pending={move.isPending} error={move.error} onClose={() => setDialog(null)}
      onSubmit={body => move.mutate({ id: dialog.target.variantId, body })} /> : null}
    {history ? <ShopMovements makerspaceId={makerspaceId} variantId={history.variantId} label={history.label} onClose={() => setHistory(null)} /> : null}
  </>;
}
