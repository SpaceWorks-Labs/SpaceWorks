import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog } from "../../../../../components/ui";
import { adapterErrorMessage, controlLabel } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Binding } from "./adaptersApi";

type Pending = { capability: string; command: string; params: Record<string, unknown>; label: string; danger?: boolean };
const UNLOCK_SECONDS = [5, 10, 30, 60];

/** Pause, resume, cancel and power for a `control` target, and unlock for a door. Each asks first; the server audits it with the staff actor. */
export function AdapterControls({ makerspaceId, adapterId, binding, name, disabled }: {
  makerspaceId: number; adapterId: string; binding: Binding; name: string; disabled: boolean;
}) {
  const client = useQueryClient();
  const [pending, setPending] = useState<Pending | null>(null);
  const [sent, setSent] = useState("");
  const [seconds, setSeconds] = useState(10);
  const run = useMutation({ mutationFn: (action: Pending) => adaptersApi.command(binding.id, action.capability, action.command, action.params),
    onSuccess: (_row, action) => { setSent(t`${action.label} sent to ${name}.`); setPending(null);
      void client.invalidateQueries({ queryKey: adapterKeys.commands(makerspaceId, adapterId) }); },
    onError: () => setPending(null) });
  const control = binding.capabilities.includes("control");
  const door = binding.capabilities.includes("door.access");
  if (!control && !door) return null;
  const choices: Pending[] = control ? [
    { capability: "control", command: "pause", params: {}, label: controlLabel("pause") }, { capability: "control", command: "resume", params: {}, label: controlLabel("resume") },
    { capability: "control", command: "cancel", params: {}, label: controlLabel("cancel"), danger: true },
    { capability: "control", command: "power", params: { on: true }, label: t`Power on` }, { capability: "control", command: "power", params: { on: false }, label: t`Power off`, danger: true }] : [];
  const unlock: Pending = { capability: "door.access", command: "unlock", params: { seconds }, label: t`Unlock door` };
  return <div className="grid gap-2 border-t border-line pt-3">
    <div className="flex flex-wrap items-end gap-2" role="group" aria-label={t`Controls for ${name}`}>
      {choices.map(choice => <button key={choice.label} type="button" className="desk-button" disabled={disabled || run.isPending}
        onClick={() => { setSent(""); setPending(choice); }}>{choice.label}</button>)}
      {door ? <>
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Unlock for`}</span>
          <select className="desk-input min-h-11" value={seconds} onChange={event => setSeconds(Number(event.target.value))}>
            {UNLOCK_SECONDS.map(value => <option key={value} value={value}>{t`${value} seconds`}</option>)}</select></label>
        <button type="button" className="desk-button" disabled={disabled || run.isPending} onClick={() => { setSent(""); setPending(unlock); }}>{unlock.label}</button></> : null}
    </div>
    {run.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(run.error)}</p> : null}
    {sent ? <p role="status" className="text-sm text-muted">{sent}</p> : null}
    <ConfirmDialog open={pending !== null} tone={pending?.danger ? "danger" : "default"} pending={run.isPending}
      title={t`${pending?.label ?? ""}: ${name}?`} confirmLabel={pending?.label ?? t`Confirm`}
      message={pending?.command === "unlock" ? t`The door opens for ${seconds} seconds. This is recorded in the audit log with your name.`
        : pending?.danger ? t`This can stop work that is in progress. The command goes to the bridge and is recorded in the audit log with your name.`
          : t`The command goes to the bridge and is recorded in the audit log with your name.`}
      onConfirm={() => { if (pending) run.mutate(pending); }} onCancel={() => setPending(null)} />
  </div>;
}
