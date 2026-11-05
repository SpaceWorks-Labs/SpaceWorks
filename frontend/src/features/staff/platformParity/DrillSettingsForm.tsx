import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { useSaveDrillSettings, type DrillSettings } from "./restoreDrillsApi";

/** Interval and archive-ready notice. Mount it with a `key` of the saved values so a save resets the draft. */
export function DrillSettingsForm({ saved }: { saved: DrillSettings }) {
  const save = useSaveDrillSettings();
  const [days, setDays] = useState(String(saved.restore_drill_interval_days));
  const [notice, setNotice] = useState(saved.archive_ready_notice_enabled);
  const interval = Number(days);
  const daysValid = days.trim() !== "" && Number.isInteger(interval) && interval >= 0 && interval <= 365;
  const dirty = interval !== saved.restore_drill_interval_days || notice !== saved.archive_ready_notice_enabled;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!daysValid || !dirty || save.isPending) return;
    save.mutate({ restore_drill_interval_days: interval, archive_ready_notice_enabled: notice },
      { onSuccess: () => toast("Drill settings saved.") });
  };
  return <form className="grid gap-4" aria-label="Restore drill settings" onSubmit={submit} noValidate>
    <Field label="Days between drills of each space" hint="0 turns scheduled drills off. At most 365."
      error={daysValid ? undefined : "Enter a whole number from 0 to 365."}>
      <input className="desk-input sm:max-w-40" type="number" inputMode="numeric" min={0} max={365} step={1} value={days}
        onChange={event => setDays(event.target.value)} />
    </Field>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={notice} onChange={event => setNotice(event.target.checked)} />
      Email the superadmins when a requested archive is ready
    </label>
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!daysValid || !dirty || save.isPending}>
      {save.isPending ? "Saving…" : "Save settings"}
    </button>
  </form>;
}
