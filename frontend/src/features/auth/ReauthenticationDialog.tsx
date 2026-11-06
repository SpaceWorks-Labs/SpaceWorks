import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorText, Field, Modal } from "../../components/ui";
import { setReauthenticationHandler } from "../../lib/api/reauthentication";
import { reauthenticationKey, reauthenticationSessionKey, reauthenticationStatus, requestEnrollmentEmail, verifyIdentity } from "./reauthenticationApi";
import { reauthenticateSocial } from "./reauthenticationSocial";
import { Fingerprint } from "lucide-react";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import { reauthenticateWithPasskey } from "./passkeys/passkeyApi";
import { isPasskeyCancelled, passkeysSupported } from "./passkeys/webauthn";

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
    else setNotice(t`Your identity provider is verified. Enter a new authenticator code to finish.`);
    void client.invalidateQueries({ queryKey: reauthenticationKey });
  } });
  // A passkey is a full step-up (possession plus user verification); a passkey-only account must use it.
  const passkey = useMutation({ mutationFn: reauthenticateWithPasskey, onSuccess: () => {
    void client.invalidateQueries({ queryKey: reauthenticationKey }); finish(true);
  } });
  const email = useMutation({ mutationFn: requestEnrollmentEmail, onSuccess: () => setNotice(t`Open the confirmation link in this browser, then enroll an authenticator at /mfa. Your pending action stays unchanged.`) });
  const pending = verify.isPending || social.isPending || email.isPending || passkey.isPending;
  const error = status.error || verify.error || social.error || email.error || (isPasskeyCancelled(passkey.error) ? null : passkey.error);
  const data = status.data;
  // A passkey-only account cannot confirm with a password alone (passkey_required), so it sees only the passkey.
  const passkeyOption = Boolean(data?.passkey_available) && passkeysSupported();
  return <Modal open={open} onClose={() => finish(false)} title={t`Confirm your identity`}
    footer={<div className="flex justify-end"><button type="button" className="desk-button w-full sm:w-auto" onClick={() => finish(false)}>{t`Cancel`}</button></div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`Verify this browser session before changing permissions or credentials. Verification lasts ten minutes.`}</p>
      {status.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading verification options…`}</p> : null}
      {passkeyOption ? <button type="button" className="desk-button-primary min-h-11 w-full gap-2" disabled={pending} onClick={() => passkey.mutate()}>
        <Fingerprint aria-hidden="true" size={20} />{passkey.isPending ? t`Waiting for your passkey…` : t`Use a passkey`}</button> : null}
      {data ? <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); verify.mutate(); }}>
        {passkeyOption && !data.mfa_enabled ? null : <>
          {data.password_available ? <Field label={t`Current password`}><input className="desk-input w-full" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></Field> : null}
          {data.mfa_enabled ? <Field label={t`Authenticator code`}><input className="desk-input w-full" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} /></Field> : null}
          {data.password_available || data.mfa_enabled ? <button className={`${passkeyOption ? "desk-button" : "desk-button-primary"} w-full`} disabled={pending}>{verify.isPending ? t`Verifying…` : t`Verify identity`}</button> : passkeyOption ? null : <p className="text-sm text-muted">{t`Google and Apple accounts: confirm the emailed enrollment link, then enroll an authenticator to verify this action. Configured OIDC providers may also verify a fresh sign-in.`}</p>}
        </>}
        {data.providers.map((provider) => <button key={provider} type="button" className="desk-button w-full" disabled={pending} onClick={() => social.mutate(provider)}>{t`Verify with ${provider}`}</button>)}
        {!data.password_available && !data.mfa_enabled && !passkeyOption ? <button type="button" className="desk-button w-full" disabled={pending} onClick={() => email.mutate()}>{t`Email a confirmation link to enroll an authenticator`}</button> : null}
      </form> : null}
      {notice ? <p role="status" className="text-sm text-ink">{notice}</p> : null}
      {error ? <ErrorText message={authErrorMessage(error)} /> : null}
    </div>
  </Modal>;
}
