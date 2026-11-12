import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field, Modal } from "../../components/ui";
import { AREA_LABELS, incidentErrorMessage, options, useRecordIncident, type Incident, type IncidentArea } from "./api";
import { draftBody, emptyDraft, IncidentFields } from "./IncidentFields";
import { BoxArt } from "../../components/BoxSpinner";

/** Staff record an incident or near miss. The area follows what it links to unless chosen here. */
export function RecordIncidentDialog({ makerspaceId, onClose, onRecorded }: {
  makerspaceId: number; onClose: () => void; onRecorded: (incident: Incident) => void;
}) {
  const record = useRecordIncident(makerspaceId);
  const [draft, setDraft] = useState(emptyDraft);
  const [area, setArea] = useState<IncidentArea | "">("");
  const [involved, setInvolved] = useState("");
  const ready = Boolean(draft.title.trim());
  return <Modal open title={t`Record an incident`} onClose={onClose}>
    <form className="grid gap-4" onSubmit={event => {
      event.preventDefault();
      if (!ready || record.isPending) return;
      record.mutate({ ...draftBody(draft), ...(area ? { area } : {}), ...(involved.trim() ? { involved_note: involved.trim() } : {}) },
        { onSuccess: incident => { onRecorded(incident); onClose(); } });
    }}>
      <IncidentFields draft={draft} onChange={patch => setDraft(current => ({ ...current, ...patch }))}
        linkHint={t`A linked machine, loan, event, room or booking also decides which area manager sees the incident.`}
        extra={<div className="grid gap-4 sm:grid-cols-2">
          <Field label={t`Area`} hint={t`Left on automatic, the area comes from the linked record.`}>
            <select className="desk-input" value={area} onChange={event => setArea(event.target.value as IncidentArea | "")}>
              <option value="">{t`Automatic`}</option>
              {options(AREA_LABELS).map(row => <option key={row.value} value={row.value}>{row.label}</option>)}
            </select>
          </Field>
          <Field label={t`Person involved (optional)`} hint={t`A name or short description.`}>
            <input className="desk-input" maxLength={200} value={involved} onChange={event => setInvolved(event.target.value)} />
          </Field>
        </div>} />
      {record.error ? <p role="alert" className="text-sm text-danger">{incidentErrorMessage(record.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!ready || record.isPending}>
          {record.isPending ? <><BoxArt size={16} mono />{t`Recording…`}</> : t`Record incident`}</button>
      </div>
    </form>
  </Modal>;
}
