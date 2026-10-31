import { useState } from "react";
import { CustomFormFields } from "../forms/CustomFormFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers } from "../forms/customFormTypes";
import { StructuredApiError } from "../../lib/api";
import type { PublicAdmission } from "./membershipAdmissionApi";
import type { InviteCheck, JoinExtras, PublicPlan } from "./joinPlansApi";

export function AdmissionJoin({ settings, signedIn, pending, error, onJoin, onSignIn, plans = [], invite = null, inviteCode = "" }: {
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
}) {
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [planId, setPlanId] = useState<number | null>(null);
  const chosen = invite?.plan_id ? null : plans.find((plan) => plan.id === planId) ?? null;
  const mode = chosen?.join_mode ?? settings.join_mode;
  const schema = chosen?.application_schema ?? settings.application_schema;
  const invited = Boolean(invite?.valid);
  const blocked = mode === "closed" || (mode === "invite_only" && !invited);
  const plan = chosen ? { name: chosen.name, amount: chosen.amount, currency: chosen.currency } : settings.default_plan;
  const paid = Number(plan?.amount ?? 0) > 0 || Number(chosen?.joining_fee ?? settings.joining_fee) > 0;
  const payFirst = paid && settings.payment_timing === "before_activation";
  const label = mode === "open" ? payFirst ? "Apply to join" : "Join instantly" : "Request to join";
  const join: JoinExtras = { ...(chosen ? { plan_id: chosen.id } : {}), ...(invited ? { invite_code: inviteCode } : {}) };
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{mode === "closed" ? "Membership applications are closed" : blocked ? "Invite-only makerspace" : "Join this makerspace"}</h2>
    <p className="mt-1 text-sm text-muted">{mode === "closed" ? "This makerspace is not accepting new members." : blocked ? "Ask a space manager for an invitation." : mode === "vouch" ? `You need ${settings.vouches_required} member vouch(es) before your application can proceed.` : mode === "approval" ? "Staff will review your application." : payFirst ? "Your membership activates after the admission charge is settled." : "You will become a member immediately."}</p>
    {invited ? <p className="mt-2 text-sm text-ink" role="status">You are joining with an invite link{invite?.plan_name ? ` for the ${invite.plan_name} plan` : ""}.</p> : null}
    {!invited && plans.length ? <fieldset className="mt-3 grid gap-2">
      <legend className="text-sm font-semibold text-ink">Choose a plan</legend>
      {plans.map((option) => <label key={option.id} className="flex min-h-11 items-start gap-2 text-sm">
        <input type="radio" name="join-plan" className="mt-1" checked={planId === option.id} onChange={() => setPlanId(option.id)} />
        <span><span className="font-semibold text-ink">{option.name}</span> · {option.amount} {option.currency.toUpperCase()}
          {option.description ? <span className="block text-muted">{option.description}</span> : null}</span>
      </label>)}
    </fieldset> : null}
    {!blocked && plan ? <p className="mt-2 text-sm text-ink">Plan: {plan.name} · {plan.amount} {plan.currency.toUpperCase()}</p> : null}
    {!blocked && Number(settings.joining_fee) > 0 ? <p className="mt-2 text-sm text-ink">Joining fee: {settings.joining_fee} {(settings.joining_fee_currency ?? settings.default_plan?.currency ?? "").toUpperCase()}</p> : null}
    {!blocked && paid ? <p className="mt-2 text-sm text-muted">{payFirst ? "Payment is required before activation. You can pay online when available, or at the space." : "Charges are recorded when your membership activates."}</p> : null}
    {!blocked && signedIn ? <form className="mt-4 grid gap-4" onSubmit={(event) => {
      event.preventDefault();
      const next = validateCustomAnswers(schema, answers);
      setErrors(next);
      if (!Object.keys(next).length) onJoin(answers, join);
    }}>
      <CustomFormFields schema={schema} answers={answers} onChange={setAnswers} disabled={pending} errors={{ ...errors, ...customAnswerErrors(error instanceof StructuredApiError ? error.body.application_answers : null) }} />
      <button className="desk-button-brand w-full sm:w-fit" disabled={pending} type="submit">{pending ? "Sending…" : label}</button>
    </form> : !blocked ? <button className="desk-button-brand mt-4 w-full sm:w-fit" onClick={onSignIn} type="button">Sign in to join</button> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-danger">{error instanceof Error ? error.message : "Unable to submit your application."}</p> : null}
  </section>;
}
