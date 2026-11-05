import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DetailLayout } from "../../../components/layouts";
import { cancelMemberShopOrder, fetchMemberShopOrder, isUnpaid, shopErrorMessage, shopKeys } from "../../shop/shopApi";
import { ShopBuyerOrderView } from "../../shop/ShopBuyerOrderView";

/** One of my shop orders. Only an unpaid order can be cancelled here; a paid one is refunded at the desk. */
export function MemberShopOrderDetail({ orderId, backHref }: { orderId: number; backHref: string }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: shopKeys.memberOrder(orderId), queryFn: () => fetchMemberShopOrder(orderId), retry: false });
  const cancel = useMutation({
    mutationFn: () => cancelMemberShopOrder(orderId),
    onSuccess: order => {
      client.setQueryData(shopKeys.memberOrder(orderId), order);
      void client.invalidateQueries({ queryKey: ["member-shop-orders"] });
    },
  });
  const order = query.data;
  return <DetailLayout back={{ label: "My shop orders", href: backHref }} title={order ? `Order #${order.id}` : "Order"}
    meta={order ? [order.space_name] : undefined}
    state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: shopErrorMessage(query.error),
      onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    actions={order && isUnpaid(order.status) ? { primary: { label: "Cancel order", tone: "danger", pending: cancel.isPending,
      pendingLabel: "Cancelling…", onClick: () => cancel.mutate(),
      confirm: { title: "Cancel this order?", message: "The items go back on sale. You have not paid anything for this order.", confirmLabel: "Cancel order" } } } : undefined}
    banner={cancel.error ? { size: "inline", tone: "danger", lead: shopErrorMessage(cancel.error) } : undefined}
    main={order ? <ShopBuyerOrderView order={order} /> : null} />;
}
