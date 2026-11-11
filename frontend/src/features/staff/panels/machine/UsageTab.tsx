import { t } from "@lingui/core/macro";
import { UsageAttributionFields } from "./UsageAttributionFields";
import { ListRow, RelativeTime } from "../../../../components/ui";
import { MachineTabContent } from "./MachineTabContent";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addMachineUsage, collectionResults, getMachineUsage, machineKeys } from "../../machinesApi";

export function UsageTab({ machineId, makerspaceId, canOperate }: {
  machineId: number;
  makerspaceId: number;
  canOperate: boolean;
}) {
  const queryClient = useQueryClient();
  const [hours, setHours] = useState("");
  const [note, setNote] = useState("");
  const [member, setMember] = useState("");
  const [startedAt, setStartedAt] = useState("");
  const usage = useQuery({
    queryKey: machineKeys.usage(machineId),
    queryFn: () => getMachineUsage(machineId),
  });
  const items = collectionResults(usage.data);
  const add = useMutation({
    mutationFn: () => addMachineUsage(machineId, { hours, note: note.trim(), member: member ? Number(member) : undefined, started_at: startedAt ? new Date(startedAt).toISOString() : undefined }),
    onSuccess: async () => {
      setHours("");
      setNote("");
      setMember("");
      setStartedAt("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: machineKeys.usage(machineId) }),
        queryClient.invalidateQueries({ queryKey: machineKeys.detail(machineId) }),
        queryClient.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) }),
      ]);
    },
  });

  return (
    <section>
      <h3 className="title-section mb-3">{t`Usage`}</h3>
      <MachineTabContent query={usage} resource={t`usage`} empty={!items.length} message={t`No usage logged yet. Add the first entry.`}>
      <div className="grid gap-2">
        {items.map((entry) => (
          <ListRow key={entry.id} title={`${entry.hours} h`} meta={<>{entry.note ? <span className="block break-words">{entry.note}</span> : null}{entry.source}{entry.logged_by_username ? ` · ${entry.logged_by_username}` : ""}</>}
            right={<RelativeTime date={entry.created_at} exact />} />
        ))}
      </div>
      </MachineTabContent>
      {canOperate ? (
        <form className="mt-3 grid gap-2 sm:grid-cols-[8rem_minmax(0,1fr)_auto] sm:items-end"
          onSubmit={(event) => { event.preventDefault(); add.mutate(); }}>
          <label className="eyebrow grid gap-1">{t`Hours`}<input className="desk-input" type="number" min="0.01" step="0.01" value={hours}
              onChange={(event) => setHours(event.target.value)} required />
          </label>
          <label className="eyebrow grid gap-1">{t`Note`}<input className="desk-input" maxLength={255} value={note}
              onChange={(event) => setNote(event.target.value)} />
          </label>
          <UsageAttributionFields machineId={machineId} member={member} startedAt={startedAt}
            onChange={value => { if (value.member !== undefined) setMember(value.member); if (value.started_at !== undefined) setStartedAt(value.started_at); }} />
          <button className="desk-button-primary" type="submit" disabled={add.isPending || !hours}>
            {add.isPending ? t`Logging...` : t`Add usage`}
          </button>
        </form>
      ) : null}
      {add.error instanceof Error ? <p className="mt-2 text-sm text-danger">{add.error.message}</p> : null}
    </section>
  );
}
