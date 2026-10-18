import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { prefillDetails, saveIntentStatus } from "./api";
import { savedDetailsKey, type FieldKey, type PrefillSelector } from "./types";

/** A/C/G call once per server form context; suggestions stay reviewable in memory. */
export function useRegistrationSavedDetails(actorId: number, selector: PrefillSelector, enabled = true) {
  const client = useQueryClient();
  const key = [...savedDetailsKey(actorId), "prefill", selector.context.makerspace_id, selector.context.event_id, selector.context.subject_kind,
    selector.context.subject_id || 0, selector.context.posting_id || 0, selector.form_id, selector.form_revision, selector.event_date_revision] as const;
  const result = useQuery({ queryKey: key, queryFn: () => prefillDetails(selector), enabled, gcTime: 0, retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false });
  useEffect(() => () => { client.removeQueries({ queryKey: [...savedDetailsKey(actorId), "prefill"] }); }, [client, actorId]);
  return result;
}

export function SaveDetailChoice({ fieldKey, sensitive, checked, onChange }: { fieldKey: FieldKey; sensitive: boolean; checked: boolean; onChange: (checked: boolean) => void }) {
  return <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} />
    <span>Save to my private details{sensitive ? " (sensitive · optional)" : ""}<span className="sr-only">: {fieldKey.replace(/_/g, " ")}</span></span></label>;
}

export function AgeReview({ asOfDate, value, locked, onSourceChange, onReviewed }: {
  asOfDate: string; value: number | null; locked: boolean; onSourceChange: (dateOfBirth: string) => void; onReviewed: () => void;
}) {
  const [dob, setDob] = useState("");
  return <fieldset className="grid gap-3"><legend className="font-semibold">Age at event start</legend>
    <p>The organiser receives your computed age. Your date of birth is privately retained as the source unless the form separately asks you to disclose it.</p>
    {!locked ? <Field label="Private date of birth"><input className="desk-input" type="date" value={dob} onChange={e => { setDob(e.target.value); onSourceChange(e.target.value); }} /></Field> : null}
    <p role="status">{value === null ? "Enter a valid date of birth to review your age." : `Age ${value} as of ${asOfDate}${locked ? " · fixed at answer lock" : ""}.`}</p>
    <button type="button" className="desk-button" disabled={value === null} onClick={onReviewed}>Confirm age and event date</button>
  </fieldset>;
}

export function SaveIntentNotice({ actorId, operationId }: { actorId: number; operationId: string }) {
  const result = useQuery({ queryKey: [...savedDetailsKey(actorId), "intent", operationId], queryFn: () => saveIntentStatus(operationId), gcTime: 0, retry: false,
    refetchInterval: query => query.state.data?.state === "pending" && document.visibilityState === "visible" ? 3000 : false });
  if (result.error) return <p role="status">Your event submission succeeded. Saved details status is temporarily unavailable.</p>;
  const state = result.data?.state;
  return <div role="status">{state === "applied" ? "Your chosen details were saved privately." : state === "failed" || state === "conflict" ? <>Your event submission succeeded. Some saved details need review. <a className="underline" href="/member/account/saved-details">Review saved details</a></> : "Your event submission succeeded. Your chosen saved details are being updated."}</div>;
}
