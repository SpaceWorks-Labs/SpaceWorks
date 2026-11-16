import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

import { Field } from "../../components/ui";
import { KIND_LABELS, options, SEVERITY_LABELS, type IncidentKind, type IncidentReport, type IncidentSeverity } from "./api";

export const LINK_KEYS = ["machine_id", "room_id", "event_id", "loan_id", "booking_id"] as const;
type LinkKey = (typeof LINK_KEYS)[number];
const LINK_LABELS: Record<LinkKey, string> = {
  machine_id: t`Machine number`, room_id: t`Room number`, event_id: t`Event number`, loan_id: t`Loan number`, booking_id: t`Booking number`,
};

export type IncidentDraft = {
  kind: IncidentKind; severity: IncidentSeverity; title: string; description: string; location: string; occurredAt: string;
  links: Record<LinkKey, string>;
};
export const emptyDraft = (): IncidentDraft => ({ kind: "incident", severity: "low", title: "", description: "", location: "",
  occurredAt: "", links: { machine_id: "", room_id: "", event_id: "", loan_id: "", booking_id: "" } });

/** The draft as the API reads it: blanks dropped, the local time as an instant, link numbers as ids. */
export function draftBody(draft: IncidentDraft): IncidentReport {
  const body: IncidentReport = { kind: draft.kind, severity: draft.severity, title: draft.title.trim() };
  if (draft.description.trim()) body.description = draft.description.trim();
  if (draft.location.trim()) body.location = draft.location.trim();
  if (draft.occurredAt) body.occurred_at = new Date(draft.occurredAt).toISOString();
  for (const key of LINK_KEYS) if (/^\d+$/.test(draft.links[key])) body[key] = Number(draft.links[key]);
  return body;
}

/** The fields a member report and a staff record share; `extra` adds the staff-only ones. */
export function IncidentFields({ draft, onChange, extra, linkHint }: {
  draft: IncidentDraft; onChange: (patch: Partial<IncidentDraft>) => void; extra?: ReactNode; linkHint: string;
}) {
  return <div className="grid gap-4">
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`What happened`}>
        <select className="desk-input" value={draft.kind} onChange={event => onChange({ kind: event.target.value as IncidentKind })}>
          {options(KIND_LABELS).map(row => <option key={row.value} value={row.value}>{row.label}</option>)}
        </select>
      </Field>
      <Field label={t`How serious`}>
        <select className="desk-input" value={draft.severity} onChange={event => onChange({ severity: event.target.value as IncidentSeverity })}>
          {options(SEVERITY_LABELS).map(row => <option key={row.value} value={row.value}>{row.label}</option>)}
        </select>
      </Field>
    </div>
    <Field label={t`Short summary`} hint={draft.kind === "near_miss" ? t`For example: "Guard left open on the bandsaw".` : undefined}>
      <input className="desk-input" required maxLength={200} value={draft.title} onChange={event => onChange({ title: event.target.value })} />
    </Field>
    <Field label={t`Details (optional)`}>
      <textarea className="desk-input min-h-24" maxLength={5000} value={draft.description}
        onChange={event => onChange({ description: event.target.value })} />
    </Field>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Where (optional)`}>
        <input className="desk-input" maxLength={200} value={draft.location} onChange={event => onChange({ location: event.target.value })} />
      </Field>
      <Field label={t`When (optional)`} hint={t`Leave blank for now.`}>
        <input className="desk-input" type="datetime-local" value={draft.occurredAt} onChange={event => onChange({ occurredAt: event.target.value })} />
      </Field>
    </div>
    {extra}
    <details className="rounded-xl border border-line bg-panel p-3">
      <summary className="cursor-pointer text-sm font-semibold">{t`Link it to a record (optional)`}</summary>
      <p className="mt-2 text-xs text-muted">{linkHint}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {LINK_KEYS.map(key => <Field key={key} label={LINK_LABELS[key]}>
          <input className="desk-input" inputMode="numeric" pattern="[0-9]*" value={draft.links[key]}
            onChange={event => onChange({ links: { ...draft.links, [key]: event.target.value.replace(/\D/g, "") } })} />
        </Field>)}
      </div>
    </details>
  </div>;
}
