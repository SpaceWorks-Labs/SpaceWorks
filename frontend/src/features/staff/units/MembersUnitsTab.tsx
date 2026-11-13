import { t } from "@lingui/core/macro";

import { Panel } from "../panels/shared";
import { ImportReviewQueue } from "./ImportReviewQueue";
import { UnitsSettings } from "./UnitsSettings";

/**
 * Members › Units: the unit tree where people work with members every day (a unit lead sees their own
 * subtree read-only), plus the review queue for imports held for a lead. The same editor sits under
 * Settings › People › Member units for the Space Manager.
 */
export function MembersUnitsTab({ makerspaceId, canManageUnits, importOn }: { makerspaceId: number; canManageUnits: boolean; importOn: boolean }) {
  return <div className="grid gap-4">
    <Panel title={t`Member units`}><UnitsSettings makerspaceId={makerspaceId} canManage={canManageUnits} /></Panel>
    {importOn ? <ImportReviewQueue makerspaceId={makerspaceId} /> : null}
  </div>;
}
