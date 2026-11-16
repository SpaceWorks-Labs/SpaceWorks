import { t } from "@lingui/core/macro";
import { registrationStatusLabel } from "../../members/registrationLabels";
import type { BroadcastCta, BroadcastDraft } from "./broadcastApi";

type Props = { draft: BroadcastDraft; patch: (value: Partial<BroadcastDraft>) => void };

/** Up to three buttons under the message: an event page, the guest's ticket, or an https link. */
export function BroadcastCtaFields({ draft, patch }: Props) {
  const updateCta = (index: number, value: BroadcastCta) => patch({ ctas: draft.ctas.map((item, i) => i === index ? value : item) });
  return <fieldset className="grid gap-2"><legend className="mb-2 text-sm font-semibold">{t`Calls to action · up to three`}</legend>
    {draft.ctas.map((cta, index) => <div key={index} className="grid gap-2 rounded-xl border border-line p-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Button label`}<input className="desk-input" required maxLength={80} value={cta.label} onChange={e => updateCta(index, { ...cta, label: e.target.value })} /></label>
      <label className="grid gap-1 text-sm">{t`Destination type`}<select className="desk-input" value={cta.kind}
        onChange={e => updateCta(index, e.target.value === "https" ? { kind: "https", label: cta.label, url: "https://" } : { kind: "navigation", label: cta.label, target: "event" })}>
        <option value="navigation">{t`Event or ticket`}</option><option value="https">{t`HTTPS link`}</option></select></label>
      {cta.kind === "https"
        ? <label className="grid gap-1 text-sm">{t`HTTPS URL`}<input className="desk-input" type="url" pattern="https://.*" required maxLength={2048} value={cta.url} onChange={e => updateCta(index, { ...cta, url: e.target.value })} /></label>
        : <label className="grid gap-1 text-sm">{t`Page`}<select className="desk-input" value={cta.target} onChange={e => updateCta(index, { ...cta, target: e.target.value as "event" | "ticket" })}>
          <option value="event">{t`Event`}</option><option value="ticket">{t`My ticket`}</option></select></label>}
      <button className="desk-button" type="button" onClick={() => patch({ ctas: draft.ctas.filter((_, i) => i !== index) })}>{t`Remove button`}</button>
    </div>)}
    <button className="desk-button justify-self-start" type="button" disabled={draft.ctas.length >= 3}
      onClick={() => patch({ ctas: [...draft.ctas, { kind: "navigation", label: t`View event`, target: "event" }] })}>{t`Add button`}</button>
  </fieldset>;
}

/** Who receives it: registration states and whether they checked in. */
export function BroadcastAudienceFields({ draft, patch }: Props) {
  return <>
    <fieldset className="grid gap-2 sm:grid-cols-3"><legend className="mb-2 text-sm font-semibold">{t`Registration states`}</legend>
      {["registered", "attended", "pending_approval", "waitlisted", "rejected", "cancelled"].map(status => <label key={status} className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" checked={draft.statuses.includes(status)} onChange={e => patch({ statuses: e.target.checked ? [...draft.statuses, status] : draft.statuses.filter(item => item !== status) })} />
        {registrationStatusLabel(status)}</label>)}
    </fieldset>
    <label className="grid gap-1 text-sm">{t`Attendance`}<select className="desk-input" value={draft.attendance} onChange={e => patch({ attendance: e.target.value })}>
      <option value="any">{t`Any`}</option><option value="attended">{t`Attended`}</option><option value="not_attended">{t`Not attended`}</option></select></label>
  </>;
}
