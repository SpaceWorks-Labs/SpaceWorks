import { t } from "@lingui/core/macro";
import { lazy, Suspense } from "react";

import { ListLayout } from "../../../components/layouts";
import { Skeleton, Tabs } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import type { Makerspace } from "../panels/shared";
import { shopAccess, shopViews, type ShopView } from "./shopAccess";
import { ShopOrders } from "./ShopOrders";
import { useRoutedSubTab } from "../useRoutedSubTab";
import { ownedAreas } from "../areaPayments/areaPaymentsApi";

const ShopPos = lazy(() => import("./ShopPos").then(m => ({ default: m.ShopPos })));
const ShopCashUp = lazy(() => import("./ShopCashUp").then(m => ({ default: m.ShopCashUp })));
const ShopCatalogue = lazy(() => import("./ShopCatalogue").then(m => ({ default: m.ShopCatalogue })));
const ShopEventOffers = lazy(() => import("./ShopEventOffers").then(m => ({ default: m.ShopEventOffers })));
const ShopStock = lazy(() => import("./ShopStock").then(m => ({ default: m.ShopStock })));
const ShopReports = lazy(() => import("./ShopReports").then(m => ({ default: m.ShopReports })));
const ShopSettingsForm = lazy(() => import("./ShopSettingsForm").then(m => ({ default: m.ShopSettingsForm })));
const PaymentsPanel = lazy(() => import("../PaymentsPanel").then(m => ({ default: m.PaymentsPanel })));

/** L22 staff Shop tab: orders and the desk for sellers; catalogue, stock, reports and settings for managers. */
export function ShopPanel({ makerspace, actions, isSuperadmin }: { makerspace: Makerspace; actions: readonly string[]; isSuperadmin: boolean }) {
  const access = shopAccess(actions, isSuperadmin, makerspace);
  // Decision 242(a): the Shop Manager's own-area Payments queue sits with the rest of the shop.
  const ownsShopMoney = ownedAreas(actions, isSuperadmin || actions.includes("view_finance")).includes("shop");
  const views: { key: ShopView | "payments"; label: string }[] = [...shopViews(access),
    ...(ownsShopMoney ? [{ key: "payments" as const, label: t`Payments` }] : [])];
  // 0.12.0 row 15: the view is the URL's last segment (`/admin/shop/pos`), so each one deep-links.
  const route = useRoutedSubTab();
  if (!views.length) return <ListLayout header={{ title: t`Shop` }} state={{ status: "ready" }} isEmpty
    empty={{ message: t`Your role does not include the shop. Ask a Space Manager for shop access.` }} body={{ kind: "rows", rows: null }} />;
  const active = views.find(row => row.key === route.segment)?.key ?? views[0].key;
  const ms = makerspace.id;
  return <div className="grid min-w-0 gap-4">
    <Tabs label={t`Shop sections`} tabs={views} activeKey={active} onChange={route.select}>
      <ScreenHelp screen={`shop.${active}`} />
      <Suspense fallback={<Skeleton className="h-40 w-full" />}>
        {active === "orders" ? <ShopOrders makerspaceId={ms} access={access} /> : null}
        {active === "pos" ? <ShopPos makerspaceId={ms} access={access} /> : null}
        {active === "cash" ? <ShopCashUp makerspaceId={ms} canManage={access.manage} onLeave={() => route.select(views[0].key)} /> : null}
        {active === "catalogue" ? <ShopCatalogue makerspaceId={ms} access={access} /> : null}
        {active === "events" ? <ShopEventOffers makerspaceId={ms} /> : null}
        {active === "stock" ? <ShopStock makerspaceId={ms} access={access} /> : null}
        {active === "reports" ? <ShopReports makerspaceId={ms} /> : null}
        {active === "settings" ? <ShopSettingsForm makerspaceId={ms} /> : null}
        {active === "payments" ? <PaymentsPanel makerspaceId={ms} actorActions={actions} isSuperadmin={isSuperadmin} area="shop" embedded /> : null}
      </Suspense>
    </Tabs>
  </div>;
}
