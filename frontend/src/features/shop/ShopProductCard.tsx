import { ShoppingBag } from "lucide-react";

import { StatusPill } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { priceRange, stockLabel, type ShopPublicProduct } from "./shopApi";
import type { CartLine } from "./useShopCart";

/** The product-level label: the single variant's, else "Sold out" only when every variant is. */
function productStock(product: ShopPublicProduct) {
  if (product.sold_out) return stockLabel({ sold_out: true, stock_label: null, stock_count: null });
  return product.variants.length === 1 ? stockLabel(product.variants[0]) : null;
}

/** A card links to the product page; a single-variant product can go straight into the basket. */
export function ShopProductCard({ product, currency, href, onAdd }: {
  product: ShopPublicProduct; currency: string; href: string; onAdd: (line: Omit<CartLine, "quantity">) => void;
}) {
  const stock = productStock(product);
  const only = product.variants.length === 1 ? product.variants[0] : null;
  return <li className="grid min-w-0 content-start gap-3 rounded-xl border border-line bg-panel p-4">
    {product.image_url ? <img src={product.image_url} alt="" loading="lazy" className="aspect-[4/3] w-full rounded-lg object-cover" />
      : <div aria-hidden="true" className="grid aspect-[4/3] w-full place-items-center rounded-lg bg-surface text-muted"><ShoppingBag size={32} /></div>}
    <div className="flex min-w-0 flex-wrap gap-2">
      {stock ? <StatusPill label={stock.label} tone={stock.tone} /> : null}
      {product.members_only ? <StatusPill label="Members only" tone="info" /> : null}
    </div>
    <h2 className="title-section break-words">
      <RouteLink href={href} className="rounded-control text-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{product.name}</RouteLink>
    </h2>
    {product.category ? <p className="text-sm text-muted">{product.category}</p> : null}
    <p className="font-semibold tabular-nums text-ink">{priceRange(product, currency)}{product.unit ? <span className="ml-1 text-sm font-normal text-muted">per {product.unit}</span> : null}</p>
    {only && !product.sold_out && !only.sold_out ? <button type="button" className="desk-button min-h-11 justify-self-start"
      aria-label={`Add ${product.name} to basket`}
      onClick={() => onAdd({ variantId: only.id, label: product.name, price: only.price, productSlug: product.slug, max: product.max_per_order })}>
      Add to basket</button>
      : <RouteLink href={href} className="desk-button min-h-11 justify-self-start">{product.sold_out ? "View item" : "Choose options"}</RouteLink>}
  </li>;
}
