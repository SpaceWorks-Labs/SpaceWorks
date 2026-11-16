import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { staffRequest } from "../../../../../lib/api";
import { getMachines, machineKeys } from "../../../machinesApi";
import type { ScheduleInput } from "../maintenanceApi";
import type { MaintenanceSpec } from "./templatesApi";
import type { StepProps } from "./wizardTypes";

const DAY = 86_400_000;
const intervalText = (item: MaintenanceSpec) => item.trigger === "days" ? t`every ${item.interval} days` : item.trigger === "usage_hours" ? t`every ${item.interval} machine hours` : t`every ${item.interval} jobs`;

/** A template maintenance row as the existing schedule body; hour and job triggers keep a 30-day calendar fallback. */
export function scheduleBody(item: MaintenanceSpec, now = new Date()): ScheduleInput {
  const days = item.trigger === "days" ? item.interval : 30;
  return { description: item.title, interval_days: days, anchor: "completion", next_due: new Date(now.getTime() + days * DAY).toISOString().slice(0, 10),
    trigger: item.trigger === "days" ? "days" : "usage", ...(item.trigger === "usage_hours" ? { usage_hours: String(item.interval) } : {}), ...(item.trigger === "job_count" ? { job_count: item.interval } : {}) };
}

/** Step 9: the template's maintenance checklist; each row is created on every machine of the type through the existing schedule endpoint. */
export function StepMaintenance({ ctx }: StepProps) {
  const type = ctx.machineType!;
  const client = useQueryClient();
  const machines = useQuery({ queryKey: machineKeys.list(ctx.makerspaceId), queryFn: () => getMachines(ctx.makerspaceId) });
  const mine = (machines.data?.results ?? []).filter(machine => machine.machine_type.id === type.id);
  const items = ctx.prefill?.maintenance ?? ctx.spec?.maintenance ?? [];
  const [done, setDone] = useState<string[]>([]);
  const create = useMutation({ mutationFn: async (item: MaintenanceSpec) => {
    await Promise.all(mine.map(machine => staffRequest(`/admin/makerspaces/${ctx.makerspaceId}/machines/${machine.id}/maintenance/schedules/`,
      { method: "POST", body: JSON.stringify(scheduleBody(item)) })));
    return item.title;
  }, onSuccess: async title => { setDone(current => [...current, title]); await client.invalidateQueries({ queryKey: ["maintenance"] }); } });
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Schedules belong to single machines. Create a checklist item here to add it to every machine of this type that exists now; add machines first, or come back after.`}</p>
    {!items.length ? <p className="text-sm text-muted">{t`The template has no maintenance checklist. Add schedules on each machine's Maintenance tab.`}</p> : null}
    <ul className="grid gap-2">{items.map(item => <li key={item.title} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-3 text-sm">
      <span className="min-w-0 break-words"><strong>{item.title}</strong> <span className="text-muted">{intervalText(item)}</span></span>
      {done.includes(item.title) ? <span role="status" className="text-success-ink">{t`Created`}</span> :
        <button type="button" className="desk-button min-h-11" disabled={!mine.length || create.isPending} onClick={() => create.mutate(item)}>
          {create.isPending && create.variables === item ? <><BoxArt size={16} mono />{t`Creating…`}</> : t`Create on every machine`}</button>}
    </li>)}</ul>
    {!mine.length && machines.isSuccess && items.length ? <p className="text-xs text-muted">{t`No machines of this type yet.`}</p> : null}
    {create.error ? <p role="alert" className="text-sm text-danger">{create.error.message}</p> : null}
  </div>;
}
