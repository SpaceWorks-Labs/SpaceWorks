import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Modal } from "../../../../../components/ui";
import type { Machine } from "../../../machinesApi";
import { PRIORITY_LABELS, useCreateWorkOrder, type WorkOrder, type WorkOrderPriority } from "./workOrdersApi";
import { BoxArt } from "../../../../../components/BoxSpinner";

/** Open a work order for a machine. With `machineId` the machine is fixed (the drawer); otherwise staff pick one. */
export function WorkOrderCreateDialog({ makerspaceId, machineId, machines = [], onClose, onCreated }: {
  makerspaceId: number; machineId?: number; machines?: Machine[]; onClose: () => void; onCreated?: (order: WorkOrder) => void;
}) {
  const create = useCreateWorkOrder(makerspaceId);
  const [subject, setSubject] = useState(machineId ? String(machineId) : "");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<WorkOrderPriority>("normal");
  const [dueOn, setDueOn] = useState("");
  const [down, setDown] = useState(false);
  const ready = !!subject && !!title.trim();
  return <Modal open title={t`New work order`} onClose={onClose}>
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={event => {
      event.preventDefault();
      if (!ready) return;
      create.mutate({ subject_type: "machine", subject_id: Number(subject), title: title.trim(), description: description.trim(), priority,
        due_on: dueOn || null, takes_machine_down: down }, { onSuccess: order => { onCreated?.(order); onClose(); } });
    }}>
      {machineId ? null : <label className="eyebrow grid gap-1 sm:col-span-2">{t`Machine`}<select className="desk-input" value={subject} onChange={event => setSubject(event.target.value)}>
        <option value="">{t`Choose a machine`}</option>{machines.map(machine => <option key={machine.id} value={machine.id}>{machine.name} · {machine.machine_type.name}</option>)}
      </select></label>}
      <label className="eyebrow grid gap-1 sm:col-span-2">{t`What needs doing`}<input className="desk-input" maxLength={200} value={title} onChange={event => setTitle(event.target.value)} autoFocus /></label>
      <label className="eyebrow grid gap-1 sm:col-span-2">{t`Details (optional)`}<textarea className="desk-input min-h-24" value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label className="eyebrow grid gap-1">{t`Priority`}<select className="desk-input" value={priority} onChange={event => setPriority(event.target.value as WorkOrderPriority)}>
        {Object.entries(PRIORITY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="eyebrow grid gap-1">{t`Due (optional)`}<input className="desk-input w-full min-w-0" type="date" value={dueOn} onChange={event => setDueOn(event.target.value)} /></label>
      <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={down} onChange={event => setDown(event.target.checked)} />
        {t`Takes the machine down (it is in maintenance while the work is in progress)`}</label>
      {create.error ? <p role="alert" className="text-sm text-danger sm:col-span-2">{create.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3 sm:col-span-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!ready || create.isPending}>{create.isPending ? <><BoxArt size={16} mono />{t`Creating…`}</> : t`Create work order`}</button>
      </div>
    </form>
  </Modal>;
}
