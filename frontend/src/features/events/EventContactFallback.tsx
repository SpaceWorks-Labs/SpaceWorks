import { t } from "@lingui/core/macro";
export function EventContactFallback({ needsPhone, needsEmail, phone, email, onPhone, onEmail, disabled }: {
  needsPhone: boolean; needsEmail: boolean; phone: string; email: string;
  onPhone: (value: string) => void; onEmail: (value: string) => void; disabled?: boolean;
}) {
  return <>
    {needsPhone ? <label className="grid gap-1 text-sm">{t`Contact phone`}<input className="desk-input" type="tel" required maxLength={64} autoComplete="tel" value={phone} disabled={disabled} onChange={(e) => onPhone(e.target.value)} /><span className="text-sm text-muted">{t`The event needs a contact number because your account has none.`}</span></label> : null}
    {needsEmail ? <label className="grid gap-1 text-sm">{t`Contact email`}<input className="desk-input" type="email" required maxLength={254} autoComplete="email" value={email} disabled={disabled} onChange={(e) => onEmail(e.target.value)} /><span className="text-sm text-muted">{t`The event needs a contact address because your account has none.`}</span></label> : null}
  </>;
}
