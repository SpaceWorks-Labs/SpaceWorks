import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FlowLayout } from "../../components/layouts";

type Confirmation = { title: string; name: string; consequence: string; onConfirm: () => void };
/** Local presentation state; the existing migration services still own each transition. */
export function useMigrationConfirmation() {
  const [task, setTask] = useState<Confirmation | null>(null);
  const [value, setValue] = useState("");
  const confirm = (next: Confirmation) => { setValue(""); setTask(next); };
  const dialog = task ? <FlowLayout presentation="dialog" open title={task.title} subject={task.name}
    state={{ status: "ready" }} current="confirm" steps={[{ key: "confirm", label: t`Confirm cutover action`, state: "current" }]}
    work={<div className="grid gap-4"><p className="text-sm text-ink">{task.consequence}</p>
      <label className="grid gap-2 text-sm">{t`Type ${task.name} to confirm`}<input className="desk-input" autoComplete="off" value={value} onChange={event => setValue(event.target.value)} /></label>
    </div>}
    footer={{ next: { label: task.title, tone: "danger", disabled: value !== task.name, disabledReason: `Type ${task.name} to continue.`,
      onClick: () => { task.onConfirm(); setTask(null); } } }} onCancel={() => setTask(null)} /> : null;
  return [confirm, dialog] as const;
}
