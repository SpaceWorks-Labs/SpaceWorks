import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "../platformSpaces/ActionDialog";
import { useRunDrill } from "./restoreDrillsApi";
import { SingleSpaceSelect, type PickedSpace } from "./SingleSpaceSelect";

/** Pick one space and queue a drill of its newest backup. */
export function RunDrillForm({ configured }: { configured: boolean }) {
  const [picked, setPicked] = useState<PickedSpace | null>(null);
  const [confirming, setConfirming] = useState(false);
  const run = useRunDrill();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (picked && configured) setConfirming(true);
  };
  const close = () => { setConfirming(false); run.reset(); };
  return <form className="grid gap-4" aria-label={t`Run a drill now`} onSubmit={submit} noValidate>
    <SingleSpaceSelect value={picked} onChange={setPicked} />
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!picked || !configured}>{t`Run a drill now`}</button>
    {confirming && picked ? <ActionDialog title={t`Run a restore drill`} confirmLabel={t`Run drill`} pending={run.isPending} error={run.error}
      onCancel={close} message={t`The newest backup of ${picked.name} is restored into an isolated database and checked. The live space is not changed.`}
      onSubmit={() => run.mutate(picked.id, { onSuccess: () => {
        toast(t`Drill queued. Its report appears below when it finishes.`);
        close();
      } })} /> : null}
  </form>;
}
