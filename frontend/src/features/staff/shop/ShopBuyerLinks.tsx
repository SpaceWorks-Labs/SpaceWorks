import { t } from "@lingui/core/macro";

import { RouteLink } from "../../../components/ui/RouteLink";

/** SH2: an order's buyer with their other orders and, for people managers, their member 360. */
export function BuyerLinks({ name, buyerId, memberHref, onOrders }: {
  name: string; buyerId?: number | null; memberHref?: string; onOrders?: (buyerId: number) => void;
}) {
  if (!buyerId) return <>{name}</>;
  return <span className="inline-flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
    {memberHref ? <RouteLink className="font-semibold underline" href={memberHref}>{name}</RouteLink> : <span>{name}</span>}
    {onOrders ? <button type="button" className="desk-button-ghost min-h-11 text-sm" onClick={() => onOrders(buyerId)}>{t`Their orders`}</button> : null}
  </span>;
}
