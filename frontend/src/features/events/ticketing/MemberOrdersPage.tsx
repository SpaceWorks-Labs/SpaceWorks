import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { ListLayout } from "../../../components/layouts";
import { StatusPill } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { useTenant, useTenantPath } from "../../../lib/tenant";
import { useTenantBootstrap } from "../../inventory/usePublicInventory";
import { MemberAuthPanel } from "../../members/MemberAuthPanel";
import { MemberOrderDetail } from "./MemberOrderDetail";
import { listOrders, money, ORDER_STATUS, ticketingKeys } from "./ticketingApi";


export function useMemberSpace() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const bootstrap = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const makerspaceId = tenant.mode === "single" ? tenant.makerspaceId : bootstrap.data?.makerspace.id;
  return { makerspaceSlug, makerspaceId: makerspaceId ?? 0, loading: bootstrap.isLoading };
}

/** My ticket orders (G27): each order, its total, and how many of its places are claimed. */
export function MemberOrdersPage() {
  const { orderId } = useParams();
  const space = useMemberSpace();
  const tenantPath = useTenantPath(space.makerspaceSlug);
  const orders = useQuery({ queryKey: ticketingKeys.orders(space.makerspaceId), enabled: Boolean(space.makerspaceId),
    queryFn: () => listOrders(space.makerspaceId), retry: false });
  if (orders.error instanceof StructuredApiError && orders.error.status === 401) {
    return <MemberAuthPanel makerspaceSlug={space.makerspaceSlug} onAuthenticated={() => { void orders.refetch(); }} />;
  }
  if (orderId && /^\d+$/.test(orderId)) return <MemberOrderDetail makerspaceId={space.makerspaceId} orderId={Number(orderId)}
    makerspaceSlug={space.makerspaceSlug} />;
  const rows = orders.data?.results ?? [];
  return <ListLayout header={{ eyebrow: "Tickets", title: "My orders" }}
    state={space.loading || orders.isLoading ? { status: "loading" } : orders.error ? { status: "error", error: orders.error.message } : { status: "ready" }}
    isEmpty={!rows.length} empty={{ message: "You have no ticket orders yet.", action: { label: "Find an event", href: tenantPath("events") } }}
    body={{ kind: "rows", rows: rows.map(order => {
      const claimed = order.seats.filter(seat => seat.status === "claimed").length;
      const live = order.seats.filter(seat => seat.status !== "void").length;
      return <a key={order.id} href={tenantPath(`member/orders/${order.id}`)}
        className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line p-4 hover:border-ink focus-visible:outline-2 focus-visible:outline-focus">
        <span className="grid gap-0.5"><span className="font-semibold text-ink">{order.event_title}</span>
          <span className="text-sm text-muted">Order #{order.id} · {money(order.total, order.currency)} · {claimed} of {live} places claimed</span></span>
        <StatusPill label={ORDER_STATUS[order.status].label} tone={ORDER_STATUS[order.status].tone} />
      </a>;
    }) }} />;
}
