import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorBlock, StatusPill } from "../../components/ui";
import { MemberPhoneVerification } from "../members/MemberPhoneVerification";
import { useSaveSmsConsent, useSmsConsent } from "./smsConsentApi";

export function SmsConsent({ makerspaceId, member = true }: { makerspaceId: number; member?: boolean }) {
  const settings = useSmsConsent(makerspaceId, true, member);
  const save = useSaveSmsConsent(makerspaceId, member);
  const [verify, setVerify] = useState(false);
  if (settings.isLoading) return <p role="status">{t`Loading SMS consent…`}</p>;
  if (settings.error || !settings.data) return <ErrorBlock error={settings.error ?? new Error(t`Couldn't load SMS consent.`)}
    onRetry={() => void settings.refetch()} />;
  const sms = settings.data.sms;
  const phone = sms.phone_masked;
  return <section aria-label={t`SMS consent`} className="grid gap-3 rounded-lg border border-line p-3">
    <div className="flex flex-wrap items-center gap-3"><h3 className="title-section">{t`SMS notifications`}</h3>
      <StatusPill label={sms.available ? t`Available` : t`Unavailable`} tone={sms.available ? "success" : "neutral"} /></div>
    <p className="text-sm text-muted">{t`Allow this space's current sender to text your verified phone. Changing your phone or sender requires fresh consent. Phone verification alone does not subscribe you.`}</p>
    <p className="text-sm text-muted">{sms.phone_masked ? t`Phone: ${phone}` : t`Phone: No phone linked`}</p>
    {!sms.available ? <p className="text-sm text-muted">{t`This space has no available SMS sender. You can still withdraw consent.`}</p> : null}
    {sms.suppressed ? <p className="text-sm text-warn-ink">{t`You replied STOP. Explicitly subscribing again lifts the block for this sender.`}</p> : null}
    {member && !sms.phone_verified ? <button type="button" className="desk-button w-fit" aria-expanded={verify} onClick={() => setVerify(value => !value)}>{t`Verify your phone first`}</button> : null}
    {member && verify ? <MemberPhoneVerification /> : null}
    {!member && !sms.phone_verified ? <p className="text-sm text-muted">{t`SMS requires a verified phone on this staff account. Member phone verification cannot verify a staff account.`}</p> : null}
    <label className="flex min-h-11 items-center gap-2 text-sm">
      <input type="checkbox" className="h-4 w-4" checked={sms.consented}
        disabled={save.isPending || (!sms.consented && (!sms.available || !sms.phone_verified))}
        onChange={event => save.mutate(event.target.checked)} />{t`Allow SMS notifications`}</label>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    {save.isSuccess ? <p role="status">{t`SMS consent saved.`}</p> : null}
  </section>;
}
