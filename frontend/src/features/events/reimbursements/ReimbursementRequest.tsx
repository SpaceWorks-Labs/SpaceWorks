import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { ReimbursementRequestFields } from "./RequestFields";
import { requestPayload, requestState } from "./requestPayload";
import { reimbursementPath, useApplicantCommand, useReimbursement } from "./api";
import { useUnsavedChanges } from "../stagedForms/UnsavedChanges";
import { commandError } from "../stagedForms/privateQueries";
import type { ReimbursementOverview, ReimbursementScope } from "./types";

export function ReimbursementRequest({ scope, onDirtyChange }: { scope: ReimbursementScope; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useReimbursement(scope);
  if (!query.data) return <p role={query.error ? "alert" : "status"}>{query.error ? commandError(query.error) : t`Loading support request…`}</p>;
  if (!query.data.available || !query.data.request_context) return <p role="status">{t`Travel support is unavailable for this event.`}</p>;
  return <RequestEditor key={query.data.request?.version ?? 0} scope={scope} overview={query.data} onDirtyChange={onDirtyChange} />;
}
function RequestEditor({ scope, overview, onDirtyChange }: { scope: ReimbursementScope; overview: ReimbursementOverview; onDirtyChange?: (dirty: boolean) => void }) {
  const context = overview.request_context!;
  const [value, setValue] = useState(() => requestState(overview.request?.submission));
  const [distance, setDistance] = useState(overview.request?.submission?.distance_km ?? "");
  const [consent, setConsent] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const mutation = useApplicantCommand(scope);
  useUnsavedChanges(dirty, onDirtyChange);
  const canSubmit = overview.allowed_actions.includes("request_submit");
  return <FormPageLayout header={{ eyebrow: t`Travel support`, title: t`Request reimbursement support` }} state={{ status: "ready" }}
    submit={{ label: t`Submit support request`, pending: mutation.isPending, disabled: !canSubmit, disabledReason: "Requests are closed for your current participation.", onClick: () => {
      try { const reimbursement_request = requestPayload(context, value, consent, distance); setError("");
        mutation.mutate({ path: `${reimbursementPath(scope)}request/submit/`, body: { expected_version: overview.request?.version ?? 0, reimbursement_request } }, { onSuccess: () => setDirty(false) });
      } catch (failure) { setError(failure instanceof Error ? failure.message : t`Check your request.`); }
    } }} form={<div className="grid gap-5"><fieldset disabled={!canSubmit || mutation.isPending} className="min-w-0"><ReimbursementRequestFields context={context} value={value}
      onChange={next => { setValue(next); setDirty(true); }} distance={distance} onDistanceChange={next => { setDistance(next); setDirty(true); }}
      consent={consent} onConsentChange={next => { setConsent(next); setDirty(true); }} /></fieldset>
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : null}
      {mutation.isSuccess ? <p role="status">{t`Your request was submitted.`}</p> : null}</div>} />;
}
