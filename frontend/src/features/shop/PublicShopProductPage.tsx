import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { PublicDetailLayout, PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import type { QueryState, StatusPillProps } from "../../components/ui";
import { chargesOn } from "../../lib/charges";
import { ShopCartDrawer } from "./ShopCartDrawer";
import { fetchProduct, fetchShop, priceRange, shopErrorMessage, shopKeys, shopMoney, stockLabel, variantLabel } from "./shopApi";
import { ShopVariantPicker } from "./ShopVariantPicker";
import { useShopCart } from "./useShopCart";
import { useShopSpace } from "./useShopSpace";

/** `/m/:slug/shop/:productSlug`: one product, its options and stock, and "Add to basket". */
export function PublicShopProductPage() {
  const { productSlug = "" } = useParams();
  const space = useShopSpace();
  const cart = useShopCart(space.slug);
  const selling = chargesOn(space.bootstrap, "shop"); // #184: shop charges off means nothing is sold
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);
  const shop = useQuery({ queryKey: shopKeys.summary(space.slug), queryFn: () => fetchShop(space.slug), enabled: Boolean(space.slug), retry: false });
  const query = useQuery({ queryKey: shopKeys.product(space.slug, productSlug), queryFn: () => fetchProduct(space.slug, productSlug),
    enabled: Boolean(space.slug && productSlug), retry: false });
  const product = query.data;
  const currency = shop.data?.currency ?? "inr";
  const firstOpen = product?.variants.find(variant => !variant.sold_out);
  const variant = product?.variants.find(row => row.id === (chosen ?? firstOpen?.id)) ?? null;
  const error = !space.slug ? new Error(t`This shop is not available.`) : shop.error ?? query.error;
  const state: QueryState = error ? { status: "error", error: shopErrorMessage(error) || t`This item is not available.`,
    onRetry: () => { void shop.refetch(); void query.refetch(); } }
    : shop.isLoading || query.isLoading ? { status: "loading" } : { status: "ready" };
  const stock = variant ? stockLabel(variant) : product?.sold_out ? { label: t`Sold out`, tone: "danger" as const } : null;
  const chips: StatusPillProps[] = [...(stock ? [stock] : []), ...(product?.members_only ? [{ label: t`Members only`, tone: "info" as const }] : [])];
  const add = () => {
    if (!product || !variant) return;
    cart.add({ variantId: variant.id, label: variantLabel(product, variant), price: variant.price, productSlug: product.slug,
      max: product.max_per_order }, quantity);
    setOpen(true);
  };
  return <div style={space.brandStyle}>
    {product ? <PageMetadata title={`${product.name} · ${space.name}`} description={product.description || product.name}
      image={product.image_url || undefined} path={space.path(`shop/${product.slug}`)} /> : null}
    <PublicLayout {...space.chrome} state={state}
      breadcrumb={[{ label: t`Shop`, href: space.path("shop") }, { label: product?.name ?? t`Item` }]}>
      <PublicDetailLayout title={product?.name ?? (state.status === "error" ? t`Item unavailable` : t`Item`)} state={state}
        cover={product?.image_url ? { src: product.image_url, alt: "" } : undefined} chips={chips}
        tagline={product && selling ? priceRange(product, currency) : undefined}
        sections={product ? [
          { id: "about", label: t`About this item`, content: <p className="whitespace-pre-wrap leading-7">{product.description || t`No description yet.`}</p> },
          ...(selling ? [{ id: "pickup", label: t`Pickup`, content: <p className="leading-7">{t`Order online, then collect it at ${space.name}`}{shop.data?.pay_online ? "." : t` and pay at the desk.`}</p> }] : []),
        ] : []}
        actionCard={{ title: t`Buy`, state: product?.sold_out || !selling ? "closed" : "open",
          note: !selling ? t`This shop is not taking orders right now.` : product?.sold_out ? t`This item is sold out.` : undefined,
          summary: variant && selling ? <p className="text-2xl font-semibold tabular-nums">{shopMoney(variant.price, currency)}
            {product?.unit ? <span className="ml-1 text-sm font-normal text-muted">per {product.unit}</span> : null}</p> : null,
          form: product ? <ShopVariantPicker product={product} currency={currency} variantId={variant?.id ?? null} quantity={quantity}
            onVariant={setChosen} onQuantity={setQuantity} /> : null,
          primary: { label: t`Add to basket`, onClick: add, disabled: !variant || variant.sold_out,
            disabledReason: !variant || variant.sold_out ? "Choose an option that is in stock." : undefined },
          secondary: cart.count && selling ? [{ label: t`View basket (${cart.count})`, onClick: () => setOpen(true) }] : undefined,
          mobileBar: { summary: product?.name ?? t`Item`, label: t`Buy` } }} />
    </PublicLayout>
    {shop.data && selling ? <ShopCartDrawer open={open} onClose={() => setOpen(false)} slug={space.slug} shop={shop.data} cart={cart} path={space.path} /> : null}
  </div>;
}
