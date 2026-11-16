import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { machineKeys } from "../staff/machinesApi";
import { setOpenToAll } from "./api";

/** The per-machine "open to all members" switch (decision 319): on, no grant is needed. Default off. */
export function OpenToAllToggle({ machineId, makerspaceId, value, canEdit }: { machineId: number; makerspaceId: number; value: boolean; canEdit: boolean }) {
  const client = useQueryClient();
  const [current, setCurrent] = useState(value);
  const save = useMutation({ mutationFn: (next: boolean) => setOpenToAll(machineId, next),
    onSuccess: async (result) => { setCurrent(result.open_to_all_members); await client.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) }); } });
  return <div className="grid gap-1">
    <label className="flex min-h-11 items-center gap-2 text-sm">
      <input type="checkbox" checked={current} disabled={!canEdit || save.isPending} onChange={event => save.mutate(event.target.checked)} />
      {t`Open to all members`}</label>
    <p className="text-sm text-muted">{current ? t`Any active member can use this machine without being given access.` : t`Members need access from a space manager before they can use this machine.`}</p>
    {save.error instanceof Error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
  </div>;
}
