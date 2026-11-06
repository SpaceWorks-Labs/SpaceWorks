import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import type { QueryState } from "../../components/ui";
import { fetchOrderStatus, shopKeys } from "./shopApi";
import { ShopBuyerOrderView } from "./ShopBuyerOrderView";
import { useShopSpace } from "./useShopSpace";

/** `/m/:slug/shop/order/:token`: a guest follows an order with the private link we emailed them. */
export function ShopOrderStatusPage() {
  const { token = "" } = useParams();
  const space = useShopSpace();
  const query = useQuery({ queryKey: shopKeys.status(space.slug, token), queryFn: () => fetchOrderStatus(space.slug, token),
    enabled: Boolean(space.slug && token), retry: false, refetchInterval: 60_000 });
  // A wrong token never says whether an order exists.
  const state: QueryState = !space.slug || query.error ? { status: "error", error: "This order link is not valid. Check the link in your email." }
    : query.isPending ? { status: "loading" } : { status: "ready" };
  return <div style={space.brandStyle}>
    <PageMetadata title={t`Your order · ${space.name}`} description={t`Your shop order.`} path={space.path("shop")} noindex />
    <PublicLayout {...space.chrome} state={state} width="narrow"
      breadcrumb={[{ label: t`Shop`, href: space.path("shop") }, { label: t`Your order` }]}
      header={{ title: t`Your order`, subtitle: query.data ? t`From ${query.data.space_name}` : undefined }}>
      {query.data ? <ShopBuyerOrderView order={query.data} /> : <span />}
    </PublicLayout>
  </div>;
}
