import { t } from "@lingui/core/macro";

import { SessionMemberSelect } from "../staff/panels/machine/sessions/SessionMemberSelect";
import { SupervisedWorkspace } from "./SupervisedWorkspace";

/** The staff machine drawer's "Supervised" tab: this machine's supervised sessions. Staff pick
 *  supervisees from the machine's member list rather than typing an account number. */
export function SupervisedMachineTab({ makerspaceId, machineId }: { makerspaceId: number; machineId: number }) {
  return <SupervisedWorkspace makerspaceId={makerspaceId} machineId={machineId}
    picker={(value, onChange) => <SessionMemberSelect machineId={machineId} value={value} onChange={onChange} label={t`Supervisee`} />} />;
}
