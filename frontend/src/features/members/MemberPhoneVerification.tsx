import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import { MessagingError } from "../messaging/MessagingFeedback";
import { BoxArt } from "../../components/BoxSpinner";

// Uses the existing authenticated phone-link OTP flow; verification never grants consent.
export function MemberPhoneVerification() {
  const client = useQueryClient();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState("");
  const start = useMutation({ mutationFn: () => memberRequest<{ detail: string }>("/auth/phone/link/start", {
    method: "POST", body: JSON.stringify({ phone }),
  }), onSuccess: () => { setSentTo(phone); setCode(""); confirm.reset(); } });
  const confirm = useMutation({ mutationFn: () => memberRequest<{ phone_e164: string; verified: boolean }>("/auth/phone/link/confirm", {
    method: "POST", body: JSON.stringify({ phone: sentTo, code }),
  }), onSuccess: () => { setPhone(""); setCode(""); setSentTo(""); return client.invalidateQueries({ queryKey: ["notify-contract"] }); } });
  const pending = start.isPending || confirm.isPending;
  return <section id="phone-verification" className="desk-panel grid gap-3 p-5">
    <h2 className="title-panel">{t`Verify your phone`}</h2>
    <p className="text-sm text-muted">{t`Link your own number using a verification code, then choose SMS consent under Channels. WhatsApp needs its own connection proof.`}</p>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); start.mutate(); }}>
      <label className="grid gap-1 text-sm font-semibold">{t`Phone number (E.164)`}<input className="desk-input" type="tel" autoComplete="tel" maxLength={32} value={phone} disabled={pending} required pattern="\+[1-9][0-9]{7,14}"
        onChange={event => { setPhone(event.target.value); setSentTo(""); confirm.reset(); }} /></label>
      <button className="desk-button w-fit" disabled={pending}>{start.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send verification code`}</button>
    </form>
    {sentTo ? <form className="grid gap-3" onSubmit={event => { event.preventDefault(); confirm.mutate(); }}>
      <p role="status" className="text-sm">{t`Verification code sent.`}</p>
      <label className="grid gap-1 text-sm font-semibold">{t`Verification code`}<input className="desk-input" inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={6} pattern="[0-9]{6}" required value={code} disabled={pending} onChange={event => setCode(event.target.value)} /></label>
      <button className="desk-button-brand w-fit" disabled={pending}>{confirm.isPending ? <><BoxArt size={16} mono />{t`Verifying…`}</> : t`Verify phone`}</button>
    </form> : null}
    <MessagingError error={start.error || confirm.error} />
    {confirm.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Phone verified. Choose your messaging consent next.`}</p> : null}
  </section>;
}
