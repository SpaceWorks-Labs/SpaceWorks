import { t } from "@lingui/core/macro";
import { useState } from "react";

import { setMachinePublicity } from "../../../machinesApi";
import { MachineCreateForm } from "../MachineCreateForm";
import type { StepProps } from "./wizardTypes";

/** Step 12: add the first machines of this type with the existing machine form; the Basics visibility choice is applied to each. */
export function StepMachines({ ctx }: StepProps) {
  const [added, setAdded] = useState(0);
  const [warning, setWarning] = useState("");
  const [round, setRound] = useState(0);
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Add the machines of this type that the space has. You can add more later from the type page.`}</p>
    {added ? <p role="status" className="text-sm text-success-ink">{t`Machines added: ${added}`}</p> : null}
    {warning ? <p role="alert" className="text-sm text-danger">{warning}</p> : null}
    <MachineCreateForm key={round} makerspaceId={ctx.makerspaceId} machineType={ctx.machineType!}
      onCreated={id => { setAdded(count => count + 1); if (ctx.publicMachines) void setMachinePublicity(id, true).catch(() => setWarning(t`A machine was added but could not be shown publicly. Change it on the machine itself.`)); }}
      onDone={() => setRound(current => current + 1)} />
  </div>;
}
