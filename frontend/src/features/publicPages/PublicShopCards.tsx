import { ShoppingBag } from "lucide-react";

import type * as Api from "../../generated/api";
import { StatusPill } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { safePublicLink } from "./PublicCollectionCards";

/** L22: a few of the space's public products on its page, each linking into the shop. */
export function PublicShopCards({ shop, slug }: { shop: Api.PublicShop; slug?: string }) {
  const base = safePublicLink(shop.collection_url) ? shop.collection_url : slug ? `/m/${slug}/shop` : "";
  if (!shop.results.length) return null;
  return <div className="grid gap-4">
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{shop.results.map(product => <li key={product.id}
      className="grid content-start gap-2 rounded-xl border border-line bg-panel p-4">
      {product.image_url ? <img src={product.image_url} alt="" loading="lazy" className="aspect-[4/3] w-full rounded-lg object-cover" />
        : <div aria-hidden="true" className="grid aspect-[4/3] w-full place-items-center rounded-lg bg-surface text-muted"><ShoppingBag size={32} /></div>}
      <h3 className="title-section break-words">{base ? <RouteLink href={`${base.replace(/\/$/, "")}/${encodeURIComponent(product.slug)}`}
        className="inline-flex min-h-11 items-center text-brand-ink underline underline-offset-4">{product.name}</RouteLink> : product.name}</h3>
      {product.price_from ? <p className="font-semibold tabular-nums">From {product.price_from}</p> : null}
      {product.sold_out ? <StatusPill label="Sold out" tone="danger" /> : null}
    </li>)}</ul>
    {base ? <RouteLink href={base} className="desk-button min-h-11 justify-self-start">Visit the shop</RouteLink> : null}
  </div>;
}
