import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field } from "../../components/ui";
import { formatTime } from "../../lib/format";
import { channelLabel } from "./channelCatalog";
import { CONSENT_VERSION, useStartChallenge, useVerifyChallenge, type Challenge, type ChannelKey } from "./channelsApi";
import { BoxArt } from "../../components/BoxSpinner";

const PHONE = /^\+[1-9][0-9]{6,14}$/;

/**
 * Connect one personal channel. Nobody types a chat ID: the server issues a single-use
 * challenge and the provider proves the account (a Telegram /start link, a Slack, Discord or
 * Mattermost sign-in, or a WhatsApp code sent to the number). Only then does an endpoint exist.
 */
export function ConnectChannel({ makerspaceId, channel, member = false, onDone }: {
  makerspaceId: number; channel: ChannelKey; member?: boolean; onDone: () => void;
}) {
  const label = channelLabel(channel);
  const whatsapp = channel === "whatsapp";
  const [consent, setConsent] = useState(false);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const start = useStartChallenge(makerspaceId, member);
  const verify = useVerifyChallenge(makerspaceId, member);
  const phoneValid = PHONE.test(phone.replace(/[\s-]/g, ""));
  const link = challenge?.connect_url?.startsWith("https://") ? challenge.connect_url : undefined;

  if (!challenge) return <form className="grid min-w-0 gap-3" aria-label={t`Connect ${label}`} onSubmit={event => {
    event.preventDefault();
    start.mutate({ channel, consent: true, consent_version: CONSENT_VERSION, ...(whatsapp ? { phone_number: phone.replace(/[\s-]/g, "") } : {}) },
      { onSuccess: setChallenge });
  }}>
    {whatsapp ? <Field label={t`WhatsApp number`} hint={t`International format with the country code, for example +14155550100.`}>
      <input className="desk-input" type="tel" autoComplete="tel" value={phone} onChange={event => setPhone(event.target.value)} />
    </Field> : null}
    <label className="flex min-h-11 items-start gap-3 text-sm">
      <input className="mt-1 h-4 w-4" type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />
      <span>{t`I agree to receive notifications from this makerspace on ${label}. I can disconnect at any time`}{whatsapp ? t` or reply STOP` : ""}.</span>
    </label>
    {start.error ? <p role="alert" className="text-sm text-danger">{start.error.message}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button className="desk-button" type="submit" disabled={!consent || (whatsapp && !phoneValid) || start.isPending}>
        {start.isPending ? <><BoxArt size={16} mono />{t`Starting…`}</> : whatsapp ? t`Send me a code` : t`Connect ${label}`}</button>
      <button className="desk-button" type="button" onClick={onDone}>{t`Cancel`}</button>
    </div>
  </form>;

  const expires = formatTime(challenge.expires_at);
  const finish = () => verify.mutate({ challengeId: challenge.challenge_id, ...(whatsapp ? { code: code.trim() } : {}) }, { onSuccess: onDone });
  return <div className="grid min-w-0 gap-3" role="group" aria-label={t`Finish connecting ${label}`}>
    {challenge.instructions ? <p className="text-sm text-ink">{challenge.instructions}</p> : null}
    {link ? <p className="text-sm"><a className="desk-button inline-flex" href={link} target={challenge.oauth_state ? "_self" : "_blank"} rel="noopener noreferrer">
      {t`Open ${label} to connect ↗`}</a></p> : null}
    <p className="text-sm text-muted">{whatsapp ? t`This code expires at ${expires}. Enter the code we sent to your WhatsApp.`
      : t`This link expires at ${expires}. When ${label} says you are connected, come back and confirm.`}</p>
    {whatsapp ? <Field label={t`Code`}><input className="desk-input" inputMode="numeric" autoComplete="one-time-code" value={code}
      onChange={event => setCode(event.target.value)} /></Field> : null}
    {verify.error ? <p role="alert" className="text-sm text-danger">{whatsapp ? verify.error.message
      : t`Not connected yet. Finish in ${label}, then confirm again. (${verify.error.message})`}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button className="desk-button" type="button" disabled={verify.isPending || (whatsapp && !code.trim())} onClick={finish}>
        {verify.isPending ? <><BoxArt size={16} mono />{t`Checking…`}</> : whatsapp ? t`Verify code` : t`I've connected`}</button>
      <button className="desk-button" type="button" onClick={onDone}>{t`Cancel`}</button>
    </div>
  </div>;
}
