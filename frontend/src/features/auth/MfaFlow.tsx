import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CenteredCardLayout } from "../../components/layouts";

import { mfaRequest, type Enrollment, type MfaChallenge, type MfaCompleted } from "./mfaApi";

export function MfaFlow({ challenge, onComplete, onCancel }: {
  challenge: MfaChallenge;
  onComplete: (result: MfaCompleted) => void;
  onCancel: () => void;
}) {
  const [code, setCode] = useState("");
  const [usingRecovery, setUsingRecovery] = useState(false);
  const [copyNotice, setCopyNotice] = useState("");
  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setCopyNotice("Copied. Store it somewhere secure."); }
    catch { setCopyNotice("Couldn't copy. Select the text and copy it manually."); }
  }
  const [enrollment, setEnrollment] = useState<Enrollment>();
  const [completed, setCompleted] = useState<MfaCompleted>();
  const enroll = useMutation({
    mutationFn: () => mfaRequest<Enrollment>("/auth/mfa/enroll", { challenge: challenge.challenge }),
    onSuccess: setEnrollment,
  });
  const verify = useMutation({
    mutationFn: () => mfaRequest<MfaCompleted>(challenge.enrollment_required ? "/auth/mfa/confirm" : "/auth/mfa/verify",
      { challenge: challenge.challenge, code }),
    onSuccess: (result) => result.recovery_codes ? setCompleted(result) : onComplete(result),
  });
  if (completed) return <CenteredCardLayout state={{ status: "ready" }}
    media={{ icon: "CheckCircle", tone: "success" }} title="Save your recovery codes"
    body="Each code works once. Save these somewhere secure; they will not be shown again."
    primary={{ label: "I saved my codes. Continue", onClick: () => onComplete(completed) }}
    content={<div className="grid gap-4">
      <ul className="grid grid-cols-2 gap-2">{completed.recovery_codes?.map((value) => <li className="rounded-control border border-line bg-surface p-3" key={value}>{value}</li>)}</ul>
      <button type="button" className="desk-button" onClick={() => void copy(completed.recovery_codes?.join("\n") ?? "")}>Copy all codes</button>
      {copyNotice ? <p role="status" className="text-sm text-muted">{copyNotice}</p> : null}
      <a className="desk-button" download="space-works-recovery-codes.txt" href={`data:text/plain;charset=utf-8,${encodeURIComponent(completed.recovery_codes?.join("\n") ?? "")}`}>Download codes</a>
    </div>} />;
  const error = enroll.error ?? verify.error;
  const canVerify = !challenge.enrollment_required || Boolean(enrollment);
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "CheckCircle", tone: "accent" }}
    title={challenge.enrollment_required ? "Set up two-step sign-in" : usingRecovery ? "Use a recovery code" : "Enter your 6-digit code"}
    body={challenge.enrollment_required ? "Add Space Works to your authenticator app to secure this account."
      : "Enter the code from your authenticator app, or one of your recovery codes."}
    primary={canVerify ? { label: "Verify", pending: verify.isPending,
      onClick: () => (document.getElementById("mfa-verify-form") as HTMLFormElement)?.requestSubmit() }
      : { label: "Show enrollment QR and key", pending: enroll.isPending, onClick: () => enroll.mutate() }}
    escape={{ label: "Back to sign-in", onClick: onCancel }}
    footer={`This sign-in expires in ${Math.ceil(challenge.expires_in / 60)} minutes. Restart sign-in if it expires.`}
    content={<div className="grid gap-4">
      {enrollment ? <>
        <img src={enrollment.qr_data_url} alt="Scan to add SpaceWorks to your authenticator" className="mx-auto w-56 rounded-xl bg-panel p-3" />
        <details><summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">Can't scan? Enter this key</summary>
          <p className="break-all select-all rounded-control border border-line p-3">{enrollment.secret}</p>
          <button type="button" className="desk-button mt-2" onClick={() => void copy(enrollment.secret)}>Copy key</button>
        </details>
      </> : null}
      {canVerify ? <form id="mfa-verify-form" className="grid gap-3" onSubmit={(event) => { event.preventDefault(); if (!verify.isPending) verify.mutate(); }}>
        <label htmlFor="mfa-code" className="text-sm font-semibold">{usingRecovery ? "Recovery code" : `Authenticator${!challenge.enrollment_required ? " or recovery" : ""} code`}</label>
        <input id="mfa-code" className="desk-input" autoComplete="one-time-code" value={code} maxLength={64} required onChange={(event) => setCode(event.target.value)} />
      <button type="submit" disabled={verify.isPending} hidden aria-hidden="true" tabIndex={-1} />
    </form> : null}
      {!challenge.enrollment_required ? <button type="button" className="desk-button-ghost" onClick={() => setUsingRecovery(!usingRecovery)}>
        {usingRecovery ? "Use an authenticator code instead" : "Use a recovery code instead"}
      </button> : null}
      {copyNotice ? <p role="status" className="text-sm text-muted">{copyNotice}</p> : null}
      {error ? <p role="alert" className="text-danger">{error.message}</p> : null}
    </div>} />;
}
