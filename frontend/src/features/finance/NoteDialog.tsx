import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field, Modal } from "../../components/ui";

/** Ask for a short note before a decision (reject a claim, record what happened). */
export function NoteDialog({ title, label, required = false, confirmLabel, onConfirm, onClose }: {
  title: string; label: string; required?: boolean; confirmLabel: string;
  onConfirm: (note: string) => void; onClose: () => void;
}) {
  const [note, setNote] = useState("");
  return <Modal open onClose={onClose} title={title}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); onConfirm(note.trim()); }}>
      <Field label={label}><textarea className="desk-input" rows={3} maxLength={300} required={required}
        value={note} onChange={event => setNote(event.target.value)} /></Field>
      <div className="flex justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button">{confirmLabel}</button>
      </div>
    </form>
  </Modal>;
}
