import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { ListLayout } from "../../../components/layouts";
import { StatusPill } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { StructuredApiError } from "../../../lib/api";
import { useTenantPath } from "../../../lib/tenant";
import { useMemberSpace } from "../../events/ticketing/MemberOrdersPage";
import { listMemberShopOrders, orderStatus, shopKeys, shopMoney } from "../../shop/shopApi";
import { MemberAuthPanel } from "../MemberAuthPanel";
import { MemberShopOrderDetail } from "./MemberShopOrderDetail";

/** My shop orders: newest first, each with its status and total; an unpaid one can be cancelled from its page. */
export function MemberShopOrdersPage() {
  const { orderId } = useParams();
  const space = useMemberSpace();
  const tenantPath = useTenantPath(space.makerspaceSlug);
  const [page, setPage] = useState(1);
  const orders = useQuery({ queryKey: shopKeys.memberOrders(space.makerspaceId, page), enabled: Boolean(space.makerspaceId),
    queryFn: () => listMemberShopOrders(space.makerspaceId, page), retry: false, placeholderData: keepPreviousData });
  if (orders.error instanceof StructuredApiError && orders.error.status === 401) {
    return <MemberAuthPanel makerspaceSlug={space.makerspaceSlug} onAuthenticated={() => { void orders.refetch(); }} />;
  }
  if (orderId && /^\d+$/.test(orderId)) return <MemberShopOrderDetail orderId={Number(orderId)} backHref={tenantPath("member/shop-orders")} />;
  const rows = orders.data?.results ?? [];
  return <ListLayout header={{ eyebrow: t`Shop`, title: t`My shop orders` }}
    state={space.loading || orders.isPending ? { status: "loading" } : orders.error ? { status: "error", error: orders.error.message,
      onRetry: () => { void orders.refetch(); } } : { status: "ready" }}
    isEmpty={!rows.length} empty={{ message: t`You have no shop orders yet.`, action: { label: t`Visit the shop`, href: tenantPath("shop") } }}
    pagination={{ page, pageSize: 24, count: orders.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: rows.map(order => {
      const status = orderStatus(order.status);
      const items = order.lines.reduce((sum, line) => sum + line.quantity, 0);
      return <RouteLink key={order.id} href={tenantPath(`member/shop-orders/${order.id}`)}
        className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line p-4 hover:border-ink focus-visible:outline-2 focus-visible:outline-focus">
        <span className="grid gap-0.5"><span className="font-semibold text-ink">{t`Order #${order.id}`}</span>
          <span className="text-sm text-muted">{items} {items === 1 ? "item" : "items"} · {shopMoney(order.total, order.currency)} · {new Date(order.created_at).toLocaleDateString(formatLocale())}</span></span>
        <StatusPill label={status.label} tone={status.tone} />
      </RouteLink>;
    }) }} />;
}
