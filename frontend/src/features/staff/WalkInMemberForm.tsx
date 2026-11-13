import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card } from "../../components/ui";
import { staffRequest, StructuredApiError } from "../../lib/api";
import { admissionStateLabel } from "../members/membershipLabels";
import { CustomFormFields } from "../forms/CustomFormFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers } from "../forms/customFormTypes";
import type { AdmissionRequest, PublicAdmission } from "../members/membershipAdmissionApi";
import { useStaffChargesOn } from "./useStaffChargesOn";
import { formatMoney, formatPrice } from "../../lib/money";
import { WalkInGuestPassResult, type WalkInGuestPass } from "../guestPasses/staff/WalkInGuestPassResult";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

type WalkInMember = { user_id: number; display_name: string; username: string; admission_request?: AdmissionRequest }
  | WalkInGuestPass;

/**
 * Name the person at the counter so a handout can be recorded against them.
 *
 * This is the identity path a deployment running without member accounts lives on, so
 * it sits inside the handout flow rather than relying on self-service enrolment.
 *
 * Collapsed by default. The normal case is picking an existing member, and an always-open
 * creation form next to a dropdown invites creating a duplicate of the person already in it.
 */
export function WalkInMemberForm({
  makerspaceId,
  onCreated,
}: {
  makerspaceId: number;
  onCreated: (userId: number) => void;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [answerErrors, setAnswerErrors] = useState<Record<string, string>>({});
  const [application, setApplication] = useState<AdmissionRequest | null>(null);
  const [guestPass, setGuestPass] = useState<WalkInGuestPass | null>(null);
  const admission = useQuery({ queryKey: ["walk-in-admission", makerspaceId], queryFn: () => staffRequest<PublicAdmission>(`/admin/makerspaces/${makerspaceId}/walk-in-members`), enabled: open, retry: false });
  const chargesOn = useStaffChargesOn("membership", makerspaceId); // #184: free membership shows no plan price or fee

  const create = useMutation({
    mutationFn: () =>
      staffRequest<WalkInMember>(`/admin/makerspaces/${makerspaceId}/walk-in-members`, {
        method: "POST",
        body: JSON.stringify({
          display_name: displayName.trim(),
          email: email.trim(),
          phone: phone.trim(),
          application_answers: answers,
        }),
      }),
    onSuccess: (member) => {
      // The dropdown reads this query, so it has to be refetched before the new member
      // can be selected — selecting an id the options don't contain leaves the select blank.
      const refresh = queryClient.invalidateQueries({ queryKey: ["direct-loan-members", makerspaceId] });
      // Decision 223 (i): the space may register walk-ins on a guest pass instead of a membership.
      if ("guest_pass_id" in member) setGuestPass(member);
      if ("admission_request" in member && member.admission_request) {
        // Pending applicants cannot be selected for a handout. The membership queue
        // owns review and receipt-based settlement before this person becomes eligible.
        setApplication(member.admission_request);
        void queryClient.invalidateQueries({ queryKey: ["members", makerspaceId] });
      } else {
        void refresh.then(() => onCreated(member.user_id));
      }
      setDisplayName("");
      setEmail("");
      setPhone("");
      setAnswers({}); setAnswerErrors({});
      setOpen(false);
    },
  });

  if (!open) {
    return (
      <>
      {application ? <div className="mt-3 rounded border border-line bg-surface p-3" role="status">
        <p className="text-sm font-semibold text-ink">{t`Walk-in application #${application.id} · ${admissionStateLabel(application.state)}`}</p>
        <p className="mt-1 text-sm text-muted">{t`Ask a membership manager to review this application`}{application.state === "awaiting_payment" ? t` and record payment with a receipt` : ""} {t` before issuing hardware. Membership activation must finish before selecting this person for the handout.`}</p>
        {application.admission_payment ? <p className="mt-2 text-sm text-ink">{t`Admission charge: ${formatMoney(application.admission_payment.amount, application.admission_payment.currency)}`}</p> : null}
      </div> : null}
      {guestPass ? <WalkInGuestPassResult makerspaceId={makerspaceId} result={guestPass} /> : null}
      <button
        className="desk-button-ghost mt-2 px-0"
        type="button"
        onClick={() => { setApplication(null); setGuestPass(null); create.reset(); setOpen(true); }}
      >
        {application || guestPass ? t`Add another walk-in` : t`Not a member yet? Add a walk-in`}
      </button>
      </>
    );
  }

  return (
    <Card className="mt-3">
      <h3 className="title-section">{t`Add a walk-in`}</h3>
      <p className="mt-1 text-xs text-muted">
        {t`Creates a person record for the handover trail. It is not an account and cannot sign in.`}</p>
      {admission.isPending ? <LogoLoader label={t`Loading admission conditions…`} size={48} className="min-h-16 py-3" /> : null}
      {admission.error ? <p className="mt-2 text-sm text-danger" role="alert">{admission.error.message}</p> : null}
      {admission.data?.join_mode === "closed" ? <p className="mt-2 text-sm text-muted">{t`Membership applications are closed.`}</p> : null}
      {admission.data?.join_mode === "vouch" ? <p className="mt-2 text-sm text-muted">{t`This application needs ${admission.data.vouches_required} member vouch(es).`}</p> : null}
      {admission.data?.default_plan ? <p className="mt-2 text-sm text-ink">{t`Default plan: ${admission.data.default_plan.name}${chargesOn ? ` · ${formatPrice(admission.data.default_plan.amount, admission.data.default_plan.currency)}` : ""}`}</p> : null}
      {chargesOn && admission.data && Number(admission.data.joining_fee) > 0 ? <p className="mt-2 text-sm text-ink">{t`Joining fee: ${formatMoney(admission.data.joining_fee, admission.data.joining_fee_currency ?? "")}`}</p> : null}
      {chargesOn && admission.data?.payment_timing === "before_activation" ? <p className="mt-2 text-sm text-muted">{t`Any admission charge must be settled before membership activates.`}</p> : null}
      <label className="mt-3 block text-sm font-medium text-ink" htmlFor="walk-in-name">
        {t`Name`}</label>
      <input
        id="walk-in-name"
        className="desk-input mt-1 w-full"
        value={displayName}
        onChange={(event) => setDisplayName(event.target.value)}
      />
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-ink" htmlFor="walk-in-email">
            {t`Email `}<span className="font-normal text-muted">(optional)</span>
          </label>
          <input
            id="walk-in-email"
            className="desk-input mt-1 w-full"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink" htmlFor="walk-in-phone">
            {t`Phone `}<span className="font-normal text-muted">(optional)</span>
          </label>
          <input
            id="walk-in-phone"
            className="desk-input mt-1 w-full"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
          />
        </div>
      </div>
      <div className="mt-3"><CustomFormFields schema={admission.data?.application_schema ?? null} answers={answers} onChange={setAnswers} errors={{ ...answerErrors, ...customAnswerErrors(create.error instanceof StructuredApiError ? create.error.body.application_answers : null) }} disabled={create.isPending} /></div>
      {create.error ? (
        <p className="mt-2 text-sm text-danger" role="alert">
          {create.error instanceof Error ? create.error.message : t`Unable to add the walk-in.`}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="desk-button-primary"
          type="button"
          disabled={!displayName.trim() || create.isPending || !admission.isSuccess || admission.data?.join_mode === "closed"}
          onClick={() => {
            const errors = validateCustomAnswers(admission.data?.application_schema ?? null, answers);
            setAnswerErrors(errors);
            if (!Object.keys(errors).length) create.mutate();
          }}
        >
          {create.isPending ? <><BoxArt size={16} mono />{t`Adding…`}</> : t`Add walk-in`}
        </button>
        <button className="desk-button" type="button" onClick={() => setOpen(false)}>
          {t`Cancel`}</button>
      </div>
    </Card>
  );
}
