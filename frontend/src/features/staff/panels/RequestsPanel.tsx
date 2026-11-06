import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import type { CalloutProps } from "../../../components/ui";
import { Queues } from "./Queues";
import { type Makerspace } from "./shared";
import { KioskReplayRecoveryPanel } from "../../kiosk/KioskReplayRecoveryPanel";
import { useKioskReplays } from "../../kiosk/useKioskReplays";

export function RequestsPanel({ makerspace, guestOnly, canSeeHardware, canViewAudit }: { makerspace: Makerspace; guestOnly: boolean; canSeeHardware: boolean; canViewAudit: boolean }) {
  return canSeeHardware ? <HardwareRequests makerspace={makerspace} guestOnly={guestOnly} canViewAudit={canViewAudit} /> : <ListLayout header={{ title: t`Requests`, subtitle: t`Machine-service queues are managed from Machines.` }} state={{ status: "ready" }} isEmpty empty={{ message: t`Open Machines to manage machine-service queues.` }} body={{ kind: "rows", rows: null }} />;
}

/** Failed kiosk handovers sit below the queue, so unresolved ones are announced at the top. */
function HardwareRequests({ makerspace, guestOnly, canViewAudit }: { makerspace: Makerspace; guestOnly: boolean; canViewAudit: boolean }) {
  const [reveal, setReveal] = useState(0);
  // Same query key as the recovery panel's default view, so this adds no request.
  const failed = useKioskReplays(makerspace.id, "unresolved", 1).data?.count ?? 0;
  const callout: CalloutProps | undefined = failed > 0 ? { size: "banner", tone: "warn",
    lead: failed === 1 ? "1 failed kiosk handover needs review." : `${failed} failed kiosk handovers need review.`,
    action: { label: t`Review failures`, onClick: () => setReveal(key => key + 1) } } : undefined;
  return <Queues makerspace={makerspace} guestOnly={guestOnly} canViewAudit={canViewAudit} callout={callout}
    recovery={<KioskReplayRecoveryPanel makerspaceId={makerspace.id} revealKey={reveal} />} />;
}
