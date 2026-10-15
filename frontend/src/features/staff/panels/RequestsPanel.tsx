import { ListLayout } from "../../../components/layouts";
import { Queues } from "./Queues";
import { type Makerspace } from "./shared";
import { KioskReplayRecoveryPanel } from "../../kiosk/KioskReplayRecoveryPanel";

export function RequestsPanel({ makerspace, guestOnly, canSeeHardware, canViewAudit }: { makerspace: Makerspace; guestOnly: boolean; canSeeHardware: boolean; canViewAudit: boolean }) {
  return canSeeHardware ? <Queues makerspace={makerspace} guestOnly={guestOnly} canViewAudit={canViewAudit} recovery={<KioskReplayRecoveryPanel makerspaceId={makerspace.id} />} /> : <ListLayout header={{ title: "Requests", subtitle: "Machine-service queues are managed from Machines." }} state={{ status: "ready" }} isEmpty empty={{ message: "Open Machines to manage machine-service queues." }} body={{ kind: "rows", rows: null }} />;
}
