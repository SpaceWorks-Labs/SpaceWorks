import { t } from "@lingui/core/macro";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import { Pagination, type QueryState } from "../../components/ui";
import { chargesOn } from "../../lib/charges";
import { ShopCartDrawer } from "./ShopCartDrawer";
import { fetchProducts, fetchShop, shopErrorMessage, shopKeys } from "./shopApi";
import { ShopProductCard } from "./ShopProductCard";
import { useShopCart } from "./useShopCart";
import { useShopSpace } from "./useShopSpace";

const PAGE_SIZE = 24;

/** `/m/:slug/shop`: the space's products for pickup, filtered by category, with a basket kept in this browser. */
export function PublicShopPage() {
  const space = useShopSpace();
  const cart = useShopCart(space.slug);
  // #184: with shop charges off the server sells nothing, so no prices, basket or checkout show.
  const selling = chargesOn(space.bootstrap, "shop");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [categories, setCategories] = useState<string[]>([]);
  const shop = useQuery({ queryKey: shopKeys.summary(space.slug), queryFn: () => fetchShop(space.slug), enabled: Boolean(space.slug), retry: false });
  const products = useQuery({ queryKey: shopKeys.products(space.slug, page, category), enabled: Boolean(space.slug && shop.data),
    queryFn: () => fetchProducts(space.slug, page, category), placeholderData: keepPreviousData });
  // Categories come from the unfiltered listing, so choosing one never hides the others.
  useEffect(() => {
    if (category || !products.data) return;
    const seen = products.data.results.map(row => row.category).filter(Boolean);
    setCategories(current => [...new Set([...current, ...seen])].sort());
  }, [category, products.data]);
  const failed = !space.slug || shop.error || products.error;
  const state: QueryState = failed ? { status: "error", error: !space.slug ? t`This shop is not available.` : shopErrorMessage(shop.error ?? products.error),
    onRetry: shop.error || products.error ? () => { void shop.refetch(); void products.refetch(); } : undefined }
    : shop.isPending || products.isPending ? { status: "loading" } : { status: "ready" };
  const rows = products.data?.results ?? [];
  const currency = shop.data?.currency ?? "inr";
  const choose = (next: string) => { setCategory(next); setPage(1); };
  return <div style={space.brandStyle}>
    <PageMetadata title={t`Shop · ${space.name}`} description={t`Things to buy from ${space.name}, for pickup at the space.`} path={space.path("shop")} />
    <PublicLayout {...space.chrome} state={state} isEmpty={!rows.length}
      empty={{ message: category ? t`Nothing in this category right now.` : t`Nothing is on sale right now. Check back soon.` }}
      breadcrumb={[{ label: space.name, href: space.path() }, { label: t`Shop` }]}
      header={{ title: t`Shop`, subtitle: t`Order online and collect at ${space.name}.`,
        primary: selling ? { label: cart.count ? t`Basket (${cart.count})` : t`Basket`, onClick: () => setOpen(true) } : undefined }}>
      <div className="grid gap-6">
        {categories.length ? <div role="group" aria-label={t`Filter by category`} className="flex flex-wrap gap-2">
          {["", ...categories].map(name => <button key={name || "all"} type="button" aria-pressed={category === name}
            className={`${category === name ? "desk-button-primary" : "desk-button"} min-h-11`} onClick={() => choose(name)}>{name || t`All`}</button>)}
        </div> : null}
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map(product => <ShopProductCard key={product.id} product={product} currency={currency}
            href={space.path(`shop/${product.slug}`)} selling={selling} onAdd={line => { cart.add(line); setOpen(true); }} />)}
        </ul>
        <Pagination page={page} totalPages={Math.ceil((products.data?.count ?? 0) / PAGE_SIZE)} count={products.data?.count}
          pageSize={PAGE_SIZE} onChange={setPage} disabled={products.isFetching} />
      </div>
    </PublicLayout>
    {shop.data && selling ? <ShopCartDrawer open={open} onClose={() => setOpen(false)} slug={space.slug} shop={shop.data} cart={cart} path={space.path} /> : null}
  </div>;
}
