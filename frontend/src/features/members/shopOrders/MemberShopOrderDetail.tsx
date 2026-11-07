import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DetailLayout } from "../../../components/layouts";
import { RouteLink } from "../../../components/ui/RouteLink";
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
  return <DetailLayout back={{ label: t`My shop orders`, href: backHref }} title={order ? t`Order #${order.id}` : t`Order`}
    meta={order ? [order.space_name] : undefined}
    state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: shopErrorMessage(query.error),
      onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    actions={order && isUnpaid(order.status) ? { primary: { label: t`Cancel order`, tone: "danger", pending: cancel.isPending,
      pendingLabel: "Cancelling…", onClick: () => cancel.mutate(),
      confirm: { title: t`Cancel this order?`, message: t`The items go back on sale. You have not paid anything for this order.`, confirmLabel: t`Cancel order` } } } : undefined}
    banner={cancel.error ? { size: "inline", tone: "danger", lead: shopErrorMessage(cancel.error) } : undefined}
    main={order ? <div className="grid gap-5"><ShopBuyerOrderView order={order} />
      <RouteLink className="desk-button justify-self-start" href={backHref.replace(/\/shop-orders$/, "/payments")}>
        {t`Payments, refunds and receipts`}</RouteLink>
    </div> : null} />;
}
