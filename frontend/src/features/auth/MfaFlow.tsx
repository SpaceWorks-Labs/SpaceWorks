import { useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { Fingerprint, KeyRound, MailCheck, Smartphone, type LucideIcon } from "lucide-react";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import { AuthStepCard } from "./AuthStepCard";
import { MfaEmailCodeResend } from "./MfaEmailCodeResend";
import { MfaRecoveryCodesStep } from "./MfaRecoveryCodesStep";
import { SWITCH_LABEL, stepCopy, usableFactors } from "./mfaFactors";
import { mfaRequest, type Enrollment, type MfaChallenge, type MfaCompleted, type MfaFactor } from "./mfaApi";
import { verifyPasskeyFactor } from "./passkeys/passkeyApi";
import { isPasskeyCancelled, passkeysSupported } from "./passkeys/webauthn";

const FACTOR_ICONS: Record<MfaFactor, LucideIcon> = { totp: Smartphone, passkey: Fingerprint, recovery: KeyRound, email_code: MailCheck };

/**
 * The second step of a sign-in: the factor picker is driven by the challenge's `factors[]`
 * (authenticator, passkey, recovery code, emailed code) and its `purpose` (`risk` explains
 * the unusual-sign-in check). An `enrollment_required` challenge sets up an authenticator.
 */
export function MfaFlow({ challenge, onComplete, onCancel, embedded = false, eyebrow, extra, turnstileSiteKey }: {
  challenge: MfaChallenge;
  onComplete: (result: MfaCompleted) => void;
  onCancel: () => void;
  /** Inside another page's card: same steps, no page chrome. */
  embedded?: boolean;
  /** The host flow's context (e.g. an invitation) and its way out, kept visible through the code step. */
  eyebrow?: string;
  extra?: ReactNode;
  /** `/api/v1/config`'s Turnstile key, for resending an emailed code behind a CAPTCHA. */
  turnstileSiteKey?: string;
}) {
  const factors = usableFactors(challenge, passkeysSupported());
  const [factor, setFactor] = useState<MfaFactor>(factors[0]);
  const [code, setCode] = useState("");
  const [copyNotice, setCopyNotice] = useState("");
  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setCopyNotice("Copied. Store it somewhere secure."); }
    catch { setCopyNotice("Couldn't copy. Select the text and copy it manually."); }
  }
  const [enrollment, setEnrollment] = useState<Enrollment>();
  const [completed, setCompleted] = useState<MfaCompleted>();
  const finish = (result: MfaCompleted) => result.recovery_codes ? setCompleted(result) : onComplete(result);
  const enroll = useMutation({
    mutationFn: () => mfaRequest<Enrollment>("/auth/mfa/enroll", { challenge: challenge.challenge }),
    onSuccess: setEnrollment,
  });
  const verify = useMutation({
    // A challenge that names its factors (S-B) is answered with the chosen one; an older one infers it.
    mutationFn: () => mfaRequest<MfaCompleted>(challenge.enrollment_required ? "/auth/mfa/confirm" : "/auth/mfa/verify",
      challenge.factors && !challenge.enrollment_required ? { challenge: challenge.challenge, code, factor } : { challenge: challenge.challenge, code }),
    onSuccess: finish,
  });
  const passkey = useMutation({ mutationFn: () => verifyPasskeyFactor<MfaCompleted>(challenge.challenge), onSuccess: finish });
  if (completed) return <MfaRecoveryCodesStep completed={completed} embedded={embedded} eyebrow={eyebrow} extra={extra}
    onContinue={() => onComplete(completed)} />;
  const failure = enroll.error ?? verify.error ?? (isPasskeyCancelled(passkey.error) ? null : passkey.error);
  const usingPasskey = factor === "passkey" && !challenge.enrollment_required;
  const canVerify = !challenge.enrollment_required || Boolean(enrollment);
  const copyText = stepCopy(challenge, factor);
  const choose = (next: MfaFactor) => { setFactor(next); setCode(""); verify.reset(); passkey.reset(); };
  return <AuthStepCard embedded={embedded} eyebrow={eyebrow} state={{ status: "ready" }}
    media={{ icon: challenge.purpose === "risk" ? "ShieldAlert" : "ShieldCheck", tone: "accent" }}
    title={copyText.title} body={copyText.body}
    primary={usingPasskey ? { label: "Use your passkey", pending: passkey.isPending, pendingLabel: "Waiting for your passkey…", onClick: () => passkey.mutate() }
      : canVerify ? { label: "Verify", pending: verify.isPending,
        onClick: () => (document.getElementById("mfa-verify-form") as HTMLFormElement)?.requestSubmit() }
      : { label: "Show enrollment QR and key", pending: enroll.isPending, onClick: () => enroll.mutate() }}
    escape={{ label: "Back to sign-in", onClick: onCancel }}
    footer={<><p>{`This sign-in expires in ${Math.ceil(challenge.expires_in / 60)} minutes. Restart sign-in if it expires.`}</p>{extra ? <div className="mt-4">{extra}</div> : null}</>}
    content={<div className="grid gap-4">
      {enrollment ? <>
        <img src={enrollment.qr_data_url} alt="Scan to add SpaceWorks to your authenticator" className="mx-auto w-56 rounded-xl bg-panel p-3" />
        <details><summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">Can't scan? Enter this key</summary>
          <p className="break-all select-all rounded-control border border-line p-3">{enrollment.secret}</p>
          <button type="button" className="desk-button mt-2" onClick={() => void copy(enrollment.secret)}>Copy key</button>
        </details>
      </> : null}
      {canVerify && !usingPasskey ? <form id="mfa-verify-form" className="grid gap-3" onSubmit={(event) => { event.preventDefault(); if (!verify.isPending) verify.mutate(); }}>
        <label htmlFor="mfa-code" className="text-sm font-semibold">{copyText.label}</label>
        <input id="mfa-code" className="desk-input" autoComplete="one-time-code" value={code} maxLength={64} required
          inputMode={factor === "recovery" || !challenge.factors ? undefined : "numeric"} onChange={(event) => setCode(event.target.value)} />
        <button type="submit" disabled={verify.isPending} hidden aria-hidden="true" tabIndex={-1} />
      </form> : null}
      {factor === "email_code" && !challenge.enrollment_required ? <MfaEmailCodeResend challenge={challenge.challenge} turnstileSiteKey={turnstileSiteKey} /> : null}
      {!challenge.enrollment_required && factors.length > 1 ? <div className="grid gap-2" role="group" aria-label="Other ways to verify">
        {factors.filter(other => other !== factor).map(other => {
          const Glyph = FACTOR_ICONS[other];
          return <button key={other} type="button" className="desk-button-ghost min-h-11 justify-start gap-2" onClick={() => choose(other)}>
            <Glyph aria-hidden="true" size={20} />{SWITCH_LABEL[other]}</button>;
        })}
      </div> : null}
      <p role="status" className="text-sm text-muted empty:hidden">{copyNotice}</p>
      {failure ? <p role="alert" className="text-danger">{authErrorMessage(failure, "Unable to verify. Try again.")}</p> : null}
    </div>} />;
}
