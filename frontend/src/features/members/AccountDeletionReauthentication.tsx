import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui/Field";
import { memberRequest } from "../../lib/api";
import { reauthenticateMemberSocial } from "../auth/reauthenticationSocial";
import { reauthenticationKey, type ReauthenticationResult } from "../auth/reauthenticationApi";
import { deletionKey } from "./accountDeletionApi";

const post = <T,>(path: string, body: object = {}) => memberRequest<T>(`/auth/reauth${path}`, { method: "POST", body: JSON.stringify(body) });

export function AccountDeletionReauthentication({ methods, onVerified }: { methods: string[]; onVerified: () => void }) {
  const [method, setMethod] = useState(methods[0] || "");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [phoneToken, setPhoneToken] = useState("");
  const [factor, setFactor] = useState<ReauthenticationResult | null>(null);
  const client = useQueryClient();
  const accept = (result: ReauthenticationResult) => {
    setPassword(""); setCode("");
    if (result.verified) {
      setFactor(null); setPhoneToken("");
      void client.invalidateQueries({ queryKey: reauthenticationKey });
      void client.invalidateQueries({ queryKey: deletionKey() });
      onVerified();
    } else if (result.factor_required && result.factor_token) setFactor(result);
  };
  const verify = useMutation({ mutationFn: async () => {
    if (factor?.factor_token) return post<ReauthenticationResult>("/social/factor", { token: factor.factor_token, code });
    if (method === "phone") return post<ReauthenticationResult>("/phone/confirm", { token: phoneToken, code });
    return post<ReauthenticationResult>("", { password, code });
  }, onSuccess: accept });
  const phone = useMutation({ mutationFn: () => post<{ token: string }>("/phone/start"), onSuccess: result => { setPhoneToken(result.token); setCode(""); verify.reset(); } });
  const social = useMutation({ mutationFn: reauthenticateMemberSocial, onSuccess: accept });
  const pending = verify.isPending || phone.isPending || social.isPending;
  const socialMethod = !["password", "totp", "phone"].includes(method);
  const passwordNeeded = !factor && (method === "password" || (method === "totp" && methods.includes("password")));
  const error = verify.error || phone.error || social.error;
  if (!methods.length) return <p>{t`There is no available sign-in method to confirm deletion. Contact your makerspace for help.`}</p>;
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Confirm your identity with a fresh sign-in. Verification lasts ten minutes.`}</p>
    <Field label={t`Verification method`}><select className="desk-input" value={method} disabled={pending} onChange={event => {
      setMethod(event.target.value); setPassword(""); setCode(""); setFactor(null); setPhoneToken("");
      verify.reset(); phone.reset(); social.reset();
    }}>{methods.map(value => <option key={value} value={value}>{value === "totp" ? t`Authenticator` : value === "phone" ? t`Phone code` : value === "password" ? t`Password` : value}</option>)}</select></Field>
    {socialMethod && !factor ? <button type="button" className="desk-button" disabled={pending} onClick={() => social.mutate(method)}>{t`Confirm with ${method}`}</button> : null}
    {method === "phone" && !factor ? <button type="button" className="desk-button" disabled={pending} onClick={() => phone.mutate()}>{phoneToken ? t`Send a new phone verification code` : t`Send phone verification code`}</button> : null}
    {factor ? <p role="status">{factor.factor_required === "totp" ? t`Enter your authenticator code.` : factor.factor_required === "phone" ? t`Enter the verification code sent to your phone.` : t`Enter the verification code sent to your email.`}</p> : null}
    {factor ? <button type="button" className="desk-button" disabled={pending} onClick={() => { setFactor(null); setCode(""); verify.reset(); social.reset(); }}>{t`Restart provider verification`}</button> : null}
    {!socialMethod || factor ? <form className="grid gap-3" onSubmit={event => { event.preventDefault(); verify.mutate(); }}>
      {passwordNeeded ? <Field label={t`Current password`}><input className="desk-input" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} /></Field> : null}
      {method === "password" || method === "totp" || phoneToken || factor ? <Field label={method === "password" ? t`Authenticator code (if enabled)` : t`Verification code`}><input className="desk-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" required={method !== "password"} value={code} onChange={event => setCode(event.target.value)} /></Field> : null}
      <button className="desk-button-primary" disabled={pending || (method === "phone" && !phoneToken)}>{pending ? t`Verifying…` : t`Verify identity for deletion`}</button>
    </form> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
  </div>;
}
