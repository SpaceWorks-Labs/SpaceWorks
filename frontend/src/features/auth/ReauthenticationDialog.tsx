import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorText, Field, Modal } from "../../components/ui";
import { setReauthenticationHandler } from "../../lib/api/reauthentication";
import { reauthenticationKey, reauthenticationSessionKey, reauthenticationStatus, requestEnrollmentEmail, verifyIdentity } from "./reauthenticationApi";
import { reauthenticateSocial } from "./reauthenticationSocial";

export function ReauthenticationDialog() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState("");
  const resolveRef = useRef<(verified: boolean) => void>(() => undefined);
  const client = useQueryClient();
  const finish = (verified: boolean) => {
    setOpen(false); setPassword(""); setCode(""); setNotice("");
    resolveRef.current(verified);
  };
  useEffect(() => {
    const remove = setReauthenticationHandler(() => new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
      setOpen(true);
      void client.invalidateQueries({ queryKey: reauthenticationKey });
    }));
    return () => { remove(); resolveRef.current(false); };
  }, [client]);
  const status = useQuery({ queryKey: reauthenticationSessionKey(), queryFn: reauthenticationStatus, enabled: open, retry: false });
  const verify = useMutation({ mutationFn: () => verifyIdentity(password, code), onSuccess: () => {
    void client.invalidateQueries({ queryKey: reauthenticationKey }); finish(true);
  } });
  const social = useMutation({ mutationFn: reauthenticateSocial, onSuccess: (result) => {
    if (result.verified) finish(true);
    else setNotice("Your identity provider is verified. Enter a new authenticator code to finish.");
    void client.invalidateQueries({ queryKey: reauthenticationKey });
  } });
  const email = useMutation({ mutationFn: requestEnrollmentEmail, onSuccess: () => setNotice("Open the confirmation link in this browser, then enroll an authenticator at /mfa. Your pending action stays unchanged.") });
  const pending = verify.isPending || social.isPending || email.isPending;
  const error = status.error || verify.error || social.error || email.error;
  return <Modal open={open} onClose={() => finish(false)} title="Confirm your identity"
    footer={<div className="flex justify-end"><button type="button" className="desk-button w-full sm:w-auto" onClick={() => finish(false)}>Cancel</button></div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">Verify this browser session before changing permissions or credentials. Verification lasts ten minutes.</p>
      {status.isLoading ? <p role="status" className="text-sm text-muted">Loading verification options...</p> : null}
      {status.data ? <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); verify.mutate(); }}>
        {status.data.password_available ? <Field label="Current password"><input className="desk-input w-full" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></Field> : null}
        {status.data.mfa_enabled ? <Field label="Authenticator code"><input className="desk-input w-full" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} /></Field> : null}
        {status.data.password_available || status.data.mfa_enabled ? <button className="desk-button-primary w-full" disabled={pending}>{verify.isPending ? "Verifying..." : "Verify identity"}</button> : <p className="text-sm text-muted">Google and Apple accounts: confirm the emailed enrollment link, then enroll an authenticator to verify this action. Configured OIDC providers may also verify a fresh sign-in.</p>}
        {status.data.providers.map((provider) => <button key={provider} type="button" className="desk-button w-full" disabled={pending} onClick={() => social.mutate(provider)}>Verify with {provider}</button>)}
        {!status.data.password_available && !status.data.mfa_enabled ? <button type="button" className="desk-button w-full" disabled={pending} onClick={() => email.mutate()}>Email a confirmation link to enroll an authenticator</button> : null}
      </form> : null}
      {notice ? <p role="status" className="text-sm text-ink">{notice}</p> : null}
      {error ? <ErrorText message={error.message} /> : null}
    </div>
  </Modal>;
}
