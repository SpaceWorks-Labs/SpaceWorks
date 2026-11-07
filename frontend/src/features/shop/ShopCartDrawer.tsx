import { t } from "@lingui/core/macro";
import { Modal } from "../../components/ui";
import { ShopCartLines } from "./ShopCartLines";
import { ShopCheckout } from "./ShopCheckout";
import type { ShopSummary } from "./shopApi";
import type { useShopCart } from "./useShopCart";
import { useMemberSession } from "./useShopSpace";

/** The basket sheet: edit lines, then check out in the same place. */
export function ShopCartDrawer({ open, onClose, slug, shop, cart, path }: {
  open: boolean; onClose: () => void; slug: string; shop: ShopSummary; cart: ReturnType<typeof useShopCart>;
  path: (part?: string) => string;
}) {
  const [session, setSession] = useMemberSession();
  return <Modal open={open} onClose={onClose} title={t`Your basket`} size="xl">
    <div className="grid gap-5">
      <ShopCartLines lines={cart.lines} currency={shop.currency} onQuantity={cart.setQuantity} onRemove={cart.remove} />
      <ShopCheckout slug={slug} shop={shop} lines={cart.lines} session={session} onSession={setSession}
        onPlaced={cart.clear} path={path} />
    </div>
  </Modal>;
}
