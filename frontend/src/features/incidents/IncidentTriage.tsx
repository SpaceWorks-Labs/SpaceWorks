import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field } from "../../components/ui";
import {
  AREA_LABELS, incidentErrorMessage, options, SEVERITY_LABELS, STATUS_LABELS, type Incident, type IncidentPatch,
  type useIncidentChange,
} from "./api";

type Triage = Required<Pick<Incident, "status" | "severity" | "area" | "resolution_note">>;

/** Triage controls: only the fields changed here are sent (PATCH is partial on the server). */
export function IncidentTriage({ incident, mutation }: {
  incident: Incident; mutation: ReturnType<typeof useIncidentChange>["triage"];
}) {
  const initial: Triage = { status: incident.status, severity: incident.severity, area: incident.area, resolution_note: incident.resolution_note };
  const [draft, setDraft] = useState(initial);
  const changes = (Object.keys(draft) as (keyof Triage)[]).filter(key => draft[key] !== initial[key]);
  const set = <K extends keyof Triage>(key: K, value: Triage[K]) => setDraft(current => ({ ...current, [key]: value }));
  const finishing = draft.status === "resolved" || draft.status === "closed";
  return <section aria-labelledby="incident-triage-title" className="grid gap-4 rounded-xl border border-line bg-panel p-4">
    <h2 id="incident-triage-title" className="title-panel">{t`Triage`}</h2>
    <form className="grid gap-4" onSubmit={event => {
      event.preventDefault();
      if (!changes.length || mutation.isPending) return;
      const body = Object.fromEntries(changes.map(key => [key, draft[key]])) as IncidentPatch;
      mutation.mutate(body);
    }}>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t`Status`}>
          <select className="desk-input" value={draft.status} onChange={event => set("status", event.target.value as Triage["status"])}>
            {options(STATUS_LABELS).map(row => <option key={row.value} value={row.value}>{row.label}</option>)}
          </select>
        </Field>
        <Field label={t`Severity`}>
          <select className="desk-input" value={draft.severity} onChange={event => set("severity", event.target.value as Triage["severity"])}>
            {options(SEVERITY_LABELS).map(row => <option key={row.value} value={row.value}>{row.label}</option>)}
          </select>
        </Field>
        <Field label={t`Area`} hint={draft.area === "other" ? t`Only the Space Manager sees incidents in Other.` : undefined}>
          <select className="desk-input" value={draft.area} onChange={event => set("area", event.target.value as Triage["area"])}>
            {options(AREA_LABELS).map(row => <option key={row.value} value={row.value}>{row.label}</option>)}
          </select>
        </Field>
      </div>
      <Field label={t`Resolution note`} hint={finishing ? t`Say what was done so the record explains itself later.` : undefined}>
        <textarea className="desk-input min-h-20" maxLength={5000} value={draft.resolution_note}
          onChange={event => set("resolution_note", event.target.value)} />
      </Field>
      {mutation.error ? <p role="alert" className="text-sm text-danger">{incidentErrorMessage(mutation.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        {changes.length ? <button type="button" className="desk-button-ghost" onClick={() => setDraft(initial)}>{t`Discard changes`}</button> : null}
        <button type="submit" className="desk-button-primary" disabled={!changes.length || mutation.isPending}>
          {mutation.isPending ? t`Saving…` : t`Save triage`}</button>
      </div>
    </form>
  </section>;
}
