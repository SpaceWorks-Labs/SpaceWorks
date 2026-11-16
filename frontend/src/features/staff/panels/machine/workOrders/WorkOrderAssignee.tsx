import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { getOperatorCandidates, machineKeys } from "../../../machinesApi";
import { useAssignWorkOrder, type WorkOrder } from "./workOrdersApi";

/**
 * Assign a work order to a staff member, reusing the machine's operator-candidate list (the
 * makerspace's active memberships). The server refuses anyone without a staff action here and the
 * reason is shown. Only machine work orders have this list, and only open orders can be reassigned.
 */
export function WorkOrderAssignee({ order, disabled }: { order: WorkOrder; disabled: boolean }) {
  const machineId = order.subject_type === "machine" ? order.subject_id : 0;
  const candidates = useQuery({ queryKey: machineKeys.operatorCandidates(machineId), enabled: machineId > 0, retry: false,
    queryFn: () => getOperatorCandidates(machineId) });
  const assign = useAssignWorkOrder();
  const rows = candidates.data ?? [];
  const current = order.assignee_id;
  return <div className="grid gap-1">
    <label className="eyebrow grid gap-1">{t`Assigned to`}<select className="desk-input" value={current ?? ""} disabled={disabled || assign.isPending || !machineId}
        onChange={event => assign.mutate({ id: order.id, assignee_id: event.target.value ? Number(event.target.value) : null })}>
        <option value="">{t`Nobody yet`}</option>
        {current && !rows.some(row => row.user_id === current) ? <option value={current}>{t`Staff member #${current}`}</option> : null}
        {rows.map(row => <option key={row.user_id} value={row.user_id}>{row.display_name}{row.display_name !== row.username ? ` (${row.username})` : ""}</option>)}
      </select>
    </label>
    {candidates.isError ? <p className="text-sm text-muted">{t`Staff choices are unavailable: ${candidates.error.message}`}</p> : null}
    {assign.error ? <p role="alert" className="text-sm text-danger">{assign.error.message}</p> : null}
  </div>;
}
