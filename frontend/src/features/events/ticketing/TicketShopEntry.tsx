import { useTenant, tenantPath, useOptionalTenant } from "../../../lib/tenant";
import { useTenantBootstrap } from "../../inventory/usePublicInventory";
import { EventTicketShop } from "./EventTicketShop";

/** The order shop on a public event page, when the space sells tickets as orders (`events.orders`). */
export function TicketShopEntry({ makerspaceSlug, publicToken, free = false }: { makerspaceSlug: string; publicToken: string; free?: boolean }) {
  const tenant = useTenant();
  const mode = useOptionalTenant()?.mode ?? "central";
  const bootstrap = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const makerspaceId = tenant.mode === "single" ? tenant.makerspaceId : bootstrap.data?.makerspace.id;
  if (!makerspaceId) return <p role="status">Loading tickets…</p>;
  return <EventTicketShop makerspaceSlug={makerspaceSlug} makerspaceId={makerspaceId} publicToken={publicToken} free={free}
    ordersHref={orderId => tenantPath(mode, makerspaceSlug, `member/orders/${orderId}`)} />;
}
