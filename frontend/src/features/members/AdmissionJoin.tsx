import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { CustomFormFields } from "../forms/CustomFormFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers } from "../forms/customFormTypes";
import { StructuredApiError } from "../../lib/api";
import { formatMoney, formatPrice } from "../../lib/money";
import type { PublicAdmission } from "./membershipAdmissionApi";
import type { InviteCheck, JoinExtras, PublicPlan } from "./joinPlansApi";
import { JoinFormExtras } from "./joinFields/JoinFormExtras";
import { EMPTY_EXTRAS, NO_EXTRAS, serverExtrasErrors, validateExtras, type JoinExtrasErrors } from "./joinFields/joinFieldsModel";
import { joinFieldsInput } from "./joinFields/uploadJoinPhoto";

export function AdmissionJoin({ settings, signedIn, pending, error, onJoin, onSignIn, plans = [], invite = null, inviteCode = "", showPrice = true, unitSlot = null, makerspaceId }: {
  settings: PublicAdmission;
  signedIn: boolean;
  pending: boolean;
  error?: unknown;
  onJoin: (answers: CustomAnswers, join: JoinExtras) => void;
  onSignIn: () => void;
  /** X8: listed plans the applicant may choose (empty when `membership.public_plans` is off). */
  plans?: PublicPlan[];
  /** X11: a checked invite link from the page URL. */
  invite?: InviteCheck | null;
  inviteCode?: string;
  /** #184: false while membership charges are off -- no plan price, joining fee or payment copy. */
  showPrice?: boolean;
  /** Parity O-B1: the unit picker, shown above the plan choice while joining is open. */
  unitSlot?: ReactNode;
  /** Parity O-B2: needed to upload a join-form photo; without it a plan's photo is not asked for. */
  makerspaceId?: number;
}) {
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [planId, setPlanId] = useState<number | null>(null);
  const [extras, setExtras] = useState(EMPTY_EXTRAS);
  const [extrasErrors, setExtrasErrors] = useState<JoinExtrasErrors>({});
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const chosen = invite?.plan_id ? null : plans.find((plan) => plan.id === planId) ?? null;
  const mode = chosen?.join_mode ?? settings.join_mode;
  const schema = chosen?.application_schema ?? settings.application_schema;
  const invited = Boolean(invite?.valid);
  const blocked = mode === "closed" || (mode === "invite_only" && !invited);
  const plan = chosen ? { name: chosen.name, amount: chosen.amount, currency: chosen.currency } : settings.default_plan;
  const paid = showPrice && (Number(plan?.amount ?? 0) > 0 || Number(chosen?.joining_fee ?? settings.joining_fee) > 0);
  const payFirst = paid && settings.payment_timing === "before_activation";
  const label = mode === "open" ? payFirst ? "Apply to join" : "Join instantly" : "Request to join";
  const join: JoinExtras = { ...(chosen ? { plan_id: chosen.id } : {}), ...(invited ? { invite_code: inviteCode } : {}) };
  // Parity O-B2: the chosen plan's photo / phone / state (an invite's plan, else the space's default plan).
  const asked = chosen?.join_fields ?? plans.find((item) => item.id === invite?.plan_id)?.join_fields ?? settings.join_fields ?? NO_EXTRAS;
  const modes = makerspaceId === undefined ? { ...asked, photo: "off" as const } : asked;
  const busy = pending || uploading;
  const submit = async () => {
    const next = validateCustomAnswers(schema, answers);
    const nextExtras = validateExtras(modes, extras);
    setErrors(next);
    setExtrasErrors(nextExtras);
    if (Object.keys(next).length || Object.keys(nextExtras).length) return;
    setUploading(true);
    setUploadError("");
    try {
      const planFor = chosen?.id ?? invite?.plan_id ?? settings.default_plan?.id;
      const fields = makerspaceId === undefined ? undefined : await joinFieldsInput(makerspaceId, modes, extras, planFor);
      onJoin(answers, { ...join, ...(fields ? { join_fields: fields } : {}) });
    } catch (failure) {
      setUploadError(failure instanceof Error ? failure.message : t`The photo did not upload. Try again.`);
    } finally {
      setUploading(false);
    }
  };
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{mode === "closed" ? t`Membership applications are closed` : blocked ? t`Invite-only makerspace` : t`Join this makerspace`}</h2>
    <p className="mt-1 text-sm text-muted">{mode === "closed" ? t`This makerspace is not accepting new members.` : blocked ? t`Ask a space manager for an invitation.` : mode === "vouch" ? t`You need ${settings.vouches_required} member vouch(es) before your application can proceed.` : mode === "approval" ? t`Staff will review your application.` : payFirst ? t`Your membership activates after the admission charge is settled.` : t`You will become a member immediately.`}</p>
    {invited ? <p className="mt-2 text-sm text-ink" role="status">{t`You are joining with an invite link`}{invite?.plan_name ? t` for the ${invite.plan_name} plan` : ""}.</p> : null}
    {!blocked ? unitSlot : null}
    {!invited && plans.length ? <fieldset className="mt-3 grid gap-2">
      <legend className="text-sm font-semibold text-ink">{t`Choose a plan`}</legend>
      {plans.map((option) => <label key={option.id} className="flex min-h-11 items-start gap-2 text-sm">
        <input type="radio" name="join-plan" className="mt-1" checked={planId === option.id} onChange={() => setPlanId(option.id)} />
        <span><span className="font-semibold text-ink">{option.name}</span>{showPrice ? ` · ${formatPrice(option.amount, option.currency)}` : ""}
          {option.description ? <span className="block text-muted">{option.description}</span> : null}</span>
      </label>)}
    </fieldset> : null}
    {!blocked && plan ? <p className="mt-2 text-sm text-ink">{t`Plan: ${plan.name}${showPrice ? ` · ${formatPrice(plan.amount, plan.currency)}` : ""}`}</p> : null}
    {!blocked && showPrice && Number(settings.joining_fee) > 0 ? <p className="mt-2 text-sm text-ink">{t`Joining fee: ${formatMoney(settings.joining_fee, settings.joining_fee_currency ?? settings.default_plan?.currency ?? "")}`}</p> : null}
    {!blocked && paid ? <p className="mt-2 text-sm text-muted">{payFirst ? t`Payment is required before activation. You can pay online when available, or at the space.` : t`Charges are recorded when your membership activates. Pay online from Payments in your member area when it is offered, or at the space.`}</p> : null}
    {!blocked && signedIn ? <form className="mt-4 grid gap-4" onSubmit={(event) => {
      event.preventDefault();
      void submit();
    }}>
      <CustomFormFields schema={schema} answers={answers} onChange={setAnswers} disabled={busy} errors={{ ...errors, ...customAnswerErrors(error instanceof StructuredApiError ? error.body.application_answers : null) }} />
      <JoinFormExtras modes={modes} value={extras} onChange={(next) => { setExtras(next); setExtrasErrors({}); }} disabled={busy}
        errors={{ ...serverExtrasErrors(error instanceof StructuredApiError ? error.body : null), ...extrasErrors }} />
      {uploadError ? <p role="alert" className="text-sm text-danger">{uploadError}</p> : null}
      <button className="desk-button-brand w-full sm:w-fit" disabled={busy} type="submit">{uploading ? t`Uploading your photo…` : pending ? t`Sending…` : label}</button>
    </form> : !blocked ? <button className="desk-button-brand mt-4 w-full sm:w-fit" onClick={onSignIn} type="button">{t`Sign in to join`}</button> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-danger">{error instanceof Error ? error.message : t`Unable to submit your application.`}</p> : null}
  </section>;
}
