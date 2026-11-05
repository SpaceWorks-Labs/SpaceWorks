import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ConfirmDialog, ListRow, StatusPill } from "../../../components/ui";
import { KIND_LABELS } from "./productDraft";
import type { ShopAccess } from "./shopAccess";
import { ShopProductForm } from "./ShopProductForm";
import { archiveProduct, listProducts, staffShopError, staffShopKeys, type ShopProduct } from "./staffShopApi";

const priceText = (product: ShopProduct) => {
  const prices = (product.variants ?? []).filter(variant => !variant.archived_at).map(variant => Number(variant.price)).sort((a, b) => a - b);
  if (!prices.length) return "No price";
  return prices[0] === prices[prices.length - 1] ? String(prices[0]) : `${prices[0]} – ${prices[prices.length - 1]}`;
};

/** Products on sale (and archived ones), each opening its form. Archiving keeps history; nothing is deleted. */
export function ShopCatalogue({ makerspaceId, access }: { makerspaceId: number; access: ShopAccess }) {
  const client = useQueryClient();
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [confirming, setConfirming] = useState<ShopProduct | null>(null);
  const query = useQuery({ queryKey: staffShopKeys.products(makerspaceId, archived, page), queryFn: () => listProducts(makerspaceId, archived, page),
    placeholderData: keepPreviousData, enabled: editing === null });
  const archive = useMutation({ mutationFn: archiveProduct, onSettled: () => setConfirming(null),
    onSuccess: () => client.invalidateQueries({ queryKey: staffShopKeys.all(makerspaceId) }) });
  if (editing !== null) return <ShopProductForm makerspaceId={makerspaceId} productId={editing === "new" ? null : editing} access={access}
    onDone={() => setEditing(null)} />;
  const rows = query.data?.results ?? [];
  return <><ListLayout header={{ eyebrow: "Shop", title: "Catalogue", subtitle: "What the shop sells, online and at the desk.",
    primary: { label: "New product", icon: "Plus", onClick: () => setEditing("new") } }}
    tabs={[{ key: "live", label: "On sale" }, { key: "archived", label: "Archived" }]} activeTab={archived ? "archived" : "live"}
    onTabChange={key => { setArchived(key === "archived"); setPage(1); }}
    callout={archive.error ? { size: "inline", tone: "danger", lead: staffShopError(archive.error) } : undefined}
    state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: staffShopError(query.error),
      onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    isEmpty={!rows.length} empty={archived ? { message: "No archived products." }
      : { message: "No products yet. Add the first thing you sell.", action: { label: "New product", onClick: () => setEditing("new") } }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: rows.map(product => {
      const stock = (product.variants ?? []).reduce((sum, variant) => sum + (variant.available ?? 0), 0);
      return <ListRow key={product.id} title={product.name}
        identity={product.image_url ? { kind: "image", src: product.image_url } : { kind: "icon", icon: "Circle", tone: "neutral" }}
        meta={<span className="text-sm text-muted">{KIND_LABELS[product.kind ?? "other"]}{product.category ? ` · ${product.category}` : ""} · {priceText(product)} · {stock} available</span>}
        right={<span className="flex flex-wrap items-center gap-2">
          {!product.is_public ? <StatusPill label="Desk only" tone="neutral" /> : null}
          {product.is_active === false && !archived ? <StatusPill label="Not on sale" tone="warn" /> : null}
          {!archived ? <button type="button" className="desk-button-danger-outline min-h-11" disabled={archive.isPending}
            aria-label={`Archive ${product.name}`} onClick={() => setConfirming(product)}>Archive</button> : null}
        </span>}
        onClick={archived ? undefined : () => setEditing(product.id)} />;
    }) }} />
    <ConfirmDialog open={confirming !== null} tone="danger" title={`Archive ${confirming?.name ?? "this product"}?`} pending={archive.isPending}
      message="It leaves the shop and the till. Past orders, receipts and stock history keep it." confirmLabel="Archive product"
      onCancel={() => setConfirming(null)} onConfirm={() => { if (confirming) archive.mutate(confirming.id); }} />
  </>;
}
