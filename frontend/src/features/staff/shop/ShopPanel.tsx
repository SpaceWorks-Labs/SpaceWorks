import { lazy, Suspense, useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { Skeleton, Tabs } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import type { Makerspace } from "../panels/shared";
import { shopAccess, shopViews, type ShopView } from "./shopAccess";
import { ShopOrders } from "./ShopOrders";

const ShopPos = lazy(() => import("./ShopPos").then(m => ({ default: m.ShopPos })));
const ShopCashUp = lazy(() => import("./ShopCashUp").then(m => ({ default: m.ShopCashUp })));
const ShopCatalogue = lazy(() => import("./ShopCatalogue").then(m => ({ default: m.ShopCatalogue })));
const ShopStock = lazy(() => import("./ShopStock").then(m => ({ default: m.ShopStock })));
const ShopReports = lazy(() => import("./ShopReports").then(m => ({ default: m.ShopReports })));
const ShopSettingsForm = lazy(() => import("./ShopSettingsForm").then(m => ({ default: m.ShopSettingsForm })));

/** L22 staff Shop tab: orders and the desk for sellers; catalogue, stock, reports and settings for managers. */
export function ShopPanel({ makerspace, actions, isSuperadmin }: { makerspace: Makerspace; actions: readonly string[]; isSuperadmin: boolean }) {
  const access = shopAccess(actions, isSuperadmin, makerspace);
  const views = shopViews(access);
  const [view, setView] = useState<ShopView>(() => views[0]?.key ?? "orders");
  if (!views.length) return <ListLayout header={{ title: "Shop" }} state={{ status: "ready" }} isEmpty
    empty={{ message: "Your role does not include the shop. Ask a Space Manager for shop access." }} body={{ kind: "rows", rows: null }} />;
  const active = views.some(row => row.key === view) ? view : views[0].key;
  const ms = makerspace.id;
  return <div className="grid min-w-0 gap-4">
    <Tabs label="Shop sections" tabs={views} activeKey={active} onChange={key => setView(key as ShopView)}>
      <ScreenHelp screen={`shop.${active}`} />
      <Suspense fallback={<Skeleton className="h-40 w-full" />}>
        {active === "orders" ? <ShopOrders makerspaceId={ms} access={access} /> : null}
        {active === "pos" ? <ShopPos makerspaceId={ms} access={access} /> : null}
        {active === "cash" ? <ShopCashUp makerspaceId={ms} canManage={access.manage} onLeave={() => setView(views[0].key)} /> : null}
        {active === "catalogue" ? <ShopCatalogue makerspaceId={ms} access={access} /> : null}
        {active === "stock" ? <ShopStock makerspaceId={ms} access={access} /> : null}
        {active === "reports" ? <ShopReports makerspaceId={ms} /> : null}
        {active === "settings" ? <ShopSettingsForm makerspaceId={ms} /> : null}
      </Suspense>
    </Tabs>
  </div>;
}
