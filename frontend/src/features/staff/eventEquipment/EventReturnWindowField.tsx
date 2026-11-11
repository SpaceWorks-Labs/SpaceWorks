import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field } from "../../../components/ui";
import { eventErrorText } from "../eventUi";
import { useReturnWindow } from "./eventEquipmentApi";

const text = (hours: number | null) => (hours ? String(hours) : "");

/**
 * Decision 221b: event loans fall due N hours after the event ends (blank = at the end).
 * Applies to loans issued after the change; the server needs event edit_details.
 */
export function EventReturnWindowField({ makerspaceId, eventId, hours }: { makerspaceId: number; eventId: number; hours: number | null }) {
  const save = useReturnWindow(makerspaceId, eventId);
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? text(hours);
  const valid = value.trim() === "" || (/^\d+$/.test(value.trim()) && Number(value) <= 720);
  const dirty = value.trim() !== text(hours);
  return <form className="grid gap-2" aria-label={t`Equipment return window`} onSubmit={(event) => {
    event.preventDefault();
    if (!valid || !dirty) return;
    save.mutate(value.trim() ? Number(value) : null, { onSuccess: () => setDraft(null) });
  }}>
    <Field label={t`Items due N hours after the event ends (blank = at event end)`}
      hint={t`Between 0 and 720 hours. Loans already handed out keep their due time.`}>
      <input className="desk-input w-full sm:max-w-40" type="number" inputMode="numeric" min={0} max={720} step={1}
        value={value} disabled={save.isPending} onChange={(event) => { setDraft(event.target.value); save.reset(); }} />
    </Field>
    <div className="flex flex-wrap items-center gap-2">
      <button className="desk-button" type="submit" disabled={!valid || !dirty || save.isPending}>
        {save.isPending ? t`Saving…` : t`Save return window`}</button>
      {dirty ? <button className="desk-button-ghost" type="button" disabled={save.isPending} onClick={() => setDraft(null)}>{t`Discard`}</button> : null}
    </div>
    {!valid ? <p className="text-sm text-danger" role="alert">{t`Enter a whole number of hours from 0 to 720, or leave it blank.`}</p> : null}
    {save.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(save.error)}</p> : null}
    {save.isSuccess && !dirty ? <p className="text-sm text-muted" role="status">{t`Return window saved.`}</p> : null}
  </form>;
}
