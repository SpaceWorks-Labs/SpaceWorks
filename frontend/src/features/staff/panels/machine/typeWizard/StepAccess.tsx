import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { setOpenToAll } from "../../../../machine-access/api";
import { MachineAccessPanel } from "../../../../machine-access/MachineAccessPanel";
import { getMachines, machineKeys } from "../../../machinesApi";
import { yesNo } from "./ReadOnlyStep";
import type { StepProps } from "./wizardTypes";

/** Step 6: who may use machines of this type, through the decision-319 screens (grants) and the per-machine open-to-all switch. */
export function StepAccess({ ctx }: StepProps) {
  const type = ctx.machineType!;
  const client = useQueryClient();
  const machines = useQuery({ queryKey: machineKeys.list(ctx.makerspaceId), queryFn: () => getMachines(ctx.makerspaceId) });
  const mine = (machines.data?.results ?? []).filter(machine => machine.machine_type.id === type.id);
  const access = ctx.prefill?.access ?? ctx.spec?.access;
  const openAll = useMutation({ mutationFn: (open: boolean) => Promise.all(mine.map(machine => setOpenToAll(machine.id, open))),
    onSuccess: () => client.invalidateQueries({ queryKey: machineKeys.list(ctx.makerspaceId) }) });
  return <div className="grid gap-4">
    {access ? <p className="text-sm text-muted">{t`The template suggests: open to all members ${yesNo(access.open_to_all_members)}, supervised use ${yesNo(access.supervised)}.`}</p> : null}
    <div className="grid gap-2 rounded-lg border border-line p-3">
      <p className="text-sm text-muted">{t`Open to all members lets any active member use a machine without being given access. It is set per machine.`}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button min-h-11" disabled={!mine.length || openAll.isPending} onClick={() => openAll.mutate(true)}>{t`Open every machine of this type`}</button>
        <button type="button" className="desk-button-ghost min-h-11" disabled={!mine.length || openAll.isPending} onClick={() => openAll.mutate(false)}>{t`Require access for every machine`}</button></div>
      {!mine.length && machines.isSuccess ? <p className="text-xs text-muted">{t`No machines of this type yet. Add them in the last step, then come back.`}</p> : null}
      {openAll.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Access updated.`}</p> : null}
      {openAll.error ? <p role="alert" className="text-sm text-danger">{openAll.error.message}</p> : null}
    </div>
    <MachineAccessPanel makerspaceId={ctx.makerspaceId} machineTypeId={type.id}
      targets={{ types: [{ id: type.id, name: type.name }], machines: mine.map(row => ({ id: row.id, name: row.name, machine_type: type.id })) }} />
  </div>;
}
