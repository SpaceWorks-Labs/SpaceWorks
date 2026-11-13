import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Modal } from "../../components/ui";
import { collectionResults, getMachines, getMachineTypes, machineKeys } from "../staff/machinesApi";
import { accessKeys, grantAccess } from "./api";
import { BoxArt } from "../../components/BoxSpinner";

/** Member register: give the selected members access to one machine or machine type (decision 319). */
export function RegisterMachineAccessBar({ makerspaceId, selected, onDone }: { makerspaceId: number; selected: number[]; onDone: () => void }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState("");
  const [expires, setExpires] = useState("");
  const [note, setNote] = useState("");
  const machines = useQuery({ queryKey: machineKeys.list(makerspaceId), queryFn: () => getMachines(makerspaceId), enabled: open });
  const types = useQuery({ queryKey: machineKeys.types(makerspaceId), queryFn: () => getMachineTypes(makerspaceId), enabled: open });
  const save = useMutation({
    mutationFn: () => {
      const [kind, id] = target.split(":");
      return grantAccess(makerspaceId, { membership_ids: selected, note, expires_at: expires ? new Date(expires).toISOString() : null,
        ...(kind === "machine" ? { machine_id: Number(id) } : { machine_type_id: Number(id) }) });
    },
    onSuccess: async (result) => {
      await client.invalidateQueries({ queryKey: accessKeys.all(makerspaceId) });
      if (!result.failed.length) { setOpen(false); setTarget(""); onDone(); }
    },
  });
  if (!selected.length) return null;
  return <>
    <button type="button" className="desk-button w-fit" onClick={() => setOpen(true)}>{t`Give machine access to ${selected.length} selected`}</button>
    <Modal open={open} title={t`Give machine access`} onClose={() => setOpen(false)}>
      <form className="grid gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
        <label className="grid gap-1 text-sm">{t`Machine or machine type`}
          <select className="desk-input" required value={target} onChange={event => setTarget(event.target.value)}>
            <option value="">{t`Choose a machine or a type`}</option>
            <optgroup label={t`Every machine of a type`}>{collectionResults(types.data).map(row => <option key={row.id} value={`type:${row.id}`}>{row.name}</option>)}</optgroup>
            <optgroup label={t`One machine`}>{(machines.data?.results ?? []).map(row => <option key={row.id} value={`machine:${row.id}`}>{row.name}</option>)}</optgroup>
          </select></label>
        <label className="grid gap-1 text-sm">{t`Access ends (optional)`}<input className="desk-input" type="date" value={expires} onChange={event => setExpires(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">{t`Note (optional)`}<input className="desk-input" maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label>
        <button className="desk-button-primary w-fit" disabled={!target || save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Give access`}</button>
        {save.data?.failed.length ? <p role="alert" className="text-sm text-danger">{t`${save.data.failed.length} members could not be given access.`}</p> : null}
        {save.error instanceof Error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
      </form>
    </Modal>
  </>;
}
