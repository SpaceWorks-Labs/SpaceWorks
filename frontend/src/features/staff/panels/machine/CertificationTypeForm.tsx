import { t } from "@lingui/core/macro";
import { useState } from "react";
import type { CertificationInput } from "../../certificationsApi";

export function CertificationTypeForm({ initial, pending, onSave, onCancel }: {
  initial: CertificationInput; pending: boolean;
  onSave: (value: CertificationInput) => void; onCancel?: () => void;
}) {
  const [value, setValue] = useState(initial);
  return <form className="grid gap-3 rounded-lg border border-line p-3" onSubmit={(event) => { event.preventDefault(); onSave(value); }}>
    <label className="grid gap-1 text-sm">{t`Certification name`}<input className="desk-input" required maxLength={200} value={value.name} onChange={(e) => setValue({ ...value, name: e.target.value })} /></label>
    <label className="grid gap-1 text-sm">{t`Description`}<textarea className="desk-input" value={value.description} onChange={(e) => setValue({ ...value, description: e.target.value })} /></label>
    <label className="grid gap-1 text-sm">{t`Validity (days; blank means no expiry)`}<input className="desk-input" type="number" min={1} value={value.validity_days ?? ""} onChange={(e) => setValue({ ...value, validity_days: e.target.value === "" ? null : Number(e.target.value) })} /></label>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={value.is_required_for_service} onChange={(e) => setValue({ ...value, is_required_for_service: e.target.checked })} />{t`Required for service requests`}</label>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={value.is_required_for_booking} onChange={(e) => setValue({ ...value, is_required_for_booking: e.target.checked })} />{t`Required for bookings`}</label>
    <p className="text-xs text-muted">{t`Requirements apply when certification gating is enabled in makerspace features. Changing validity affects new grants and renewals.`}</p>
    <div className="flex flex-wrap gap-2"><button className="desk-button-primary" disabled={pending}>{pending ? t`Saving…` : t`Save certification`}</button>{onCancel ? <button className="desk-button-ghost" type="button" onClick={onCancel}>{t`Cancel`}</button> : null}</div>
  </form>;
}
