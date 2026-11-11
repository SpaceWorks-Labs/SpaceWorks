import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui/Field";
import { prefillDetails, saveIntentStatus } from "./api";
import { savedDetailsKey, type FieldKey, type FormSaveIntent, type FormSlot, type PrefillSelector, type SaveIntent } from "./types";

/** A/C/G call once per server form context; suggestions stay reviewable in memory. */
export function useRegistrationSavedDetails(actorId: number, selector: PrefillSelector, enabled = true) {
  const key = [...savedDetailsKey(actorId), "prefill", selector.context.makerspace_id, selector.context.event_id, selector.context.subject_kind,
    selector.context.subject_id || 0, selector.context.posting_id || 0, selector.context.stage_form_id || 0,
    selector.context.creation_operation_id || "", selector.form_id, selector.form_revision, selector.event_date_revision] as const;
  const result = useQuery({ queryKey: key, queryFn: () => prefillDetails(selector), enabled, gcTime: 0, retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false });
  // gcTime:0 clears this observer's private context on unmount/key change.
  // Removing the actor's whole prefix would also evict other active stage forms.
  return result;
}

export function SaveDetailChoice({ fieldKey, sensitive, checked, onChange }: { fieldKey: FieldKey; sensitive: boolean; checked: boolean; onChange: (checked: boolean) => void }) {
  return <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} />
    <span>{t`Save to my private details`}{sensitive ? t` (sensitive · optional)` : ""}<span className="sr-only">: {fieldKey.replace(/_/g, " ")}</span></span></label>;
}

export function AgeReview({ asOfDate, value, locked, onSourceChange, onReviewed }: {
  asOfDate: string; value: number | null; locked: boolean; onSourceChange: (dateOfBirth: string) => void; onReviewed: () => void;
}) {
  const [dob, setDob] = useState("");
  return <fieldset className="grid gap-3"><legend className="font-semibold">{t`Age at event start`}</legend>
    <p>{t`The organiser receives your computed age. Your date of birth is privately retained as the source unless the form separately asks you to disclose it.`}</p>
    {!locked ? <Field label={t`Private date of birth`}><input className="desk-input" type="date" value={dob} onChange={e => { setDob(e.target.value); onSourceChange(e.target.value); }} /></Field> : null}
    <p role="status">{value === null ? t`Enter a valid date of birth to review your age.` : (locked ? t`Age ${value} as of ${asOfDate} · fixed at answer lock.` : t`Age ${value} as of ${asOfDate}.`)}</p>
    <button type="button" className="desk-button" disabled={value === null} onClick={onReviewed}>{t`Confirm age and event date`}</button>
  </fieldset>;
}

export function SaveIntentNotice({ actorId, operationId, initialStatus }: { actorId: number; operationId: string; initialStatus?: SaveIntent }) {
  const client = useQueryClient();
  const refreshed = useRef("");
  const result = useQuery({ queryKey: [...savedDetailsKey(actorId), "intent", operationId], queryFn: () => saveIntentStatus(operationId), gcTime: 0, retry: false,
    initialData: initialStatus, enabled: !initialStatus || initialStatus.state === "pending", refetchOnWindowFocus: false, refetchOnReconnect: false,
    refetchInterval: query => query.state.data?.state === "pending" && document.visibilityState === "visible" ? 3000 : false });
  useEffect(() => {
    const state = result.data?.state;
    const token = `${actorId}:${operationId}:${state}`;
    if (state && state !== "pending" && refreshed.current !== token) {
      refreshed.current = token;
      void client.invalidateQueries({ queryKey: savedDetailsKey(actorId), exact: true });
      client.removeQueries({ queryKey: [...savedDetailsKey(actorId), "prefill"], type: "inactive" });
    }
  }, [actorId, client, operationId, result.data?.state]);
  if (result.error) return <p role="status">{t`Your event submission succeeded. Saved details status is temporarily unavailable.`}</p>;
  const state = result.data?.state;
  return <div role="status">{state === "applied" ? t`Your chosen details were saved privately.` : state === "failed" || state === "conflict" ? <>{t`Your event submission succeeded. Some saved details need review. `}<a className="underline" href="/member/account/saved-details">{t`Review saved details`}</a></> : t`Your event submission succeeded. Your chosen saved details are being updated.`}</div>;
}

/** G/R mount once after canonical submission; each form polls its own child ID. */
export function FormSaveIntentsNotice({ actorId, intents, formLabels = {} }: {
  actorId: number; intents: FormSaveIntent[]; formLabels?: Partial<Record<FormSlot, string>>;
}) {
  if (!intents.length) return null;
  return <section aria-label={t`Saved details updates`}><ul className="grid gap-3">
    {intents.map((intent, index) => <li key={intent.operation_id} className="rounded-xl border border-line bg-panel p-4 text-ink">
      <p className="font-semibold">{formLabels[intent.slot] || (intent.slot === "base" ? t`Registration form` : t`Additional form ${index + 1}`)}</p>
      {intent.state === "not_requested" ? <p>{t`No details selected for saving.`}</p> : <SaveIntentNotice actorId={actorId} operationId={intent.operation_id}
        initialStatus={{ operation_id: intent.operation_id, state: intent.state, fields: intent.fields, retryable: intent.state === "pending" }} />}
    </li>)}
  </ul></section>;
}
