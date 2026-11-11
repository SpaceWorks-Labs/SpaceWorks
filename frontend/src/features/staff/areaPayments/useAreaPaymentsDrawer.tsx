import { t } from "@lingui/core/macro";
import { lazy, Suspense, useContext, useState, type ReactNode } from "react";

import { DetailLayout } from "../../../components/layouts";
import { Skeleton } from "../../../components/ui";
import type { Action } from "../../../components/ui/types";
import { StaffListContext } from "../StaffListContext";
import { areaLabel, ownedAreas, type AreaKey } from "./areaPaymentsApi";

const PaymentsPanel = lazy(() => import("../PaymentsPanel").then(m => ({ default: m.PaymentsPanel })));

/**
 * Decision 242(a): the area's own Payments queue inside its console. Returns an overflow entry and its
 * drawer, like `useDomainSettingsDialog`, so a console adds it with one spread and one render. The entry
 * shows only when the signed-in staff member owns a charge type in this area (or holds finance); the
 * server narrows every row to their own subjects and machine types.
 */
export function useAreaPaymentsDrawer(makerspaceId: number, area: AreaKey): { actions: Action[]; dialog: ReactNode } {
  const { actions = [], isSuperadmin = false } = useContext(StaffListContext);
  const [open, setOpen] = useState(false);
  const allowed = ownedAreas(actions, isSuperadmin || actions.includes("view_finance")).includes(area);
  return {
    actions: allowed ? [{ label: t`Payments`, onClick: () => setOpen(true) }] : [],
    dialog: allowed && open ? <DetailLayout presentation="drawer" open onClose={() => setOpen(false)}
      title={t`${areaLabel(area)} payments`} state={{ status: "ready" }}
      main={<Suspense fallback={<Skeleton className="h-40 w-full" />}>
        <PaymentsPanel makerspaceId={makerspaceId} actorActions={actions} isSuperadmin={isSuperadmin} area={area} embedded />
      </Suspense>} /> : null,
  };
}
