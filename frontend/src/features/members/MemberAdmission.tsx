import { formatDate, formatDateTime } from "../../lib/format";
import { formatMoney, paymentStatusLabel } from "../staff/paymentsApi";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import { CustomAnswersView } from "../forms/CustomAnswersView";
import { cancelAdmission, vouchForAdmission, type AdmissionRequest } from "./membershipAdmissionApi";
import { admissionStateLabel } from "./membershipLabels";
import { ApplicationChanges } from "./ApplicationChanges";

export function MemberAdmission({ makerspaceId, request }: { makerspaceId: number; request: AdmissionRequest }) {
  const client = useQueryClient();
  const cancel = useMutation({ mutationFn: () => cancelAdmission(makerspaceId, request.id), onSuccess: () => client.invalidateQueries({ queryKey: ["member"] }) });
  const download = useMutation({ mutationFn: () => memberRequest<unknown>(`/member/makerspaces/${makerspaceId}/admission/export`), onSuccess: (data) => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = "membership-applications.json"; link.click();
    URL.revokeObjectURL(url);
  } });
  const pending = ["requested", "awaiting_vouches", "awaiting_payment", "changes_requested"].includes(request.state);
  const changes = request.state === "changes_requested"; // parity O-B2
  const stateWords = admissionStateLabel(request.state);
  const title = request.state === "awaiting_payment" ? t`Membership awaiting payment` : request.state === "awaiting_vouches" ? t`Membership awaiting vouches` : request.state === "requested" ? t`Membership request sent` : changes ? t`Your application needs changes` : t`Membership application: ${stateWords}`;
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{title}</h2>
    {changes ? <ApplicationChanges key={`${request.id}:${request.edit_schema !== undefined}`} makerspaceId={makerspaceId} request={request} /> : <p className="mt-2 text-sm text-muted">{request.state === "awaiting_payment" ? t`Your membership activates when the admission charge is settled. Use the Payments tab, or pay at the space.` : request.state === "awaiting_vouches" ? t`Share application number ${request.id} with an eligible member, who can vouch from their member area.` : request.state === "requested" ? t`Staff will review your request.` : t`This is the latest recorded state of your application.`}</p>}
    {request.admission_payment ? <p className="mt-2 text-sm text-ink">{t`Admission charge: ${formatMoney(request.admission_payment.amount, request.admission_payment.currency)} · ${paymentStatusLabel(request.admission_payment.status)}`}</p> : null}
    {pending && request.expires_at ? <p className="mt-2 text-sm text-muted">{t`Application expires ${formatDateTime(request.expires_at)}.`}</p> : null}
    {request.vouches?.length ? <ul className="mt-3 break-words text-sm text-muted">{request.vouches.map((vouch) => <li key={vouch.voucher_id}>{t`Vouched by ${vouch.voucher_name} · expires ${formatDate(vouch.expires_at)}`}</li>)}</ul> : null}
    {request.application_answers?.answers.length ? <details className="mt-3"><summary className="cursor-pointer text-sm font-semibold text-ink">{t`Your application answers`}</summary><div className="mt-3"><CustomAnswersView snapshot={request.application_answers} /></div></details> : null}
    <div className="mt-4 flex flex-wrap gap-3 [&>button]:flex-1 sm:[&>button]:flex-none">
      {pending ? <button type="button" className="desk-button-danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>{t`Cancel application`}</button> : null}
      <button type="button" className="desk-button-brand" disabled={download.isPending} onClick={() => download.mutate()}>{t`Download application data`}</button>
    </div>
    {cancel.error || download.error ? <p className="mt-3 text-sm text-danger" role="alert">{(cancel.error ?? download.error)?.message}</p> : null}
  </section>;
}

export function MemberVouch({ makerspaceId }: { makerspaceId: number }) {
  const [requestId, setRequestId] = useState("");
  const client = useQueryClient();
  const vouch = useMutation({ mutationFn: () => vouchForAdmission(makerspaceId, Number(requestId)), onSuccess: () => client.invalidateQueries({ queryKey: ["member"] }) });
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{t`Vouch for an applicant`}</h2>
    <p className="mt-1 text-sm text-muted">{t`Ask the applicant for their application number. Your vouch is recorded permanently with your identity. Eligibility, tenure and pending-applicant limits apply.`}</p>
    <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); vouch.mutate(); }}>
      <label className="grid min-w-0 flex-1 basis-48 gap-1 text-sm text-ink sm:max-w-xs">{t`Application number`}<input className="desk-input w-full" type="number" inputMode="numeric" required min="1" step="1" value={requestId} onChange={(event) => { setRequestId(event.target.value); vouch.reset(); }} /></label>
      <button className="desk-button-brand w-full sm:w-auto" type="submit" disabled={vouch.isPending || !requestId}>{t`Record my vouch`}</button>
    </form>
    {vouch.isSuccess ? <p className="mt-3 text-sm text-success-ink" role="status">{t`Your vouch is recorded.`}</p> : null}
    {vouch.error ? <p className="mt-3 text-sm text-danger" role="alert">{vouch.error.message}</p> : null}
  </section>;
}
