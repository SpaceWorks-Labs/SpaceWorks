import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Field, Modal } from "../../../components/ui";
import { guestErrorText, operationId } from "../../guestPasses/api";
import { communityStaffApi, type Consent, type MinorInput, type MinorProfile } from "../api";

/** Record (or update) a person as a minor, with a birth date or an "under age" declaration. */
export function RecordMinorDialog({ makerspaceId, onClose, onSaved }: { makerspaceId: number; onClose: () => void; onSaved: () => void }) {
  const [person, setPerson] = useState("");
  const [birth, setBirth] = useState("");
  const [declared, setDeclared] = useState(false);
  const [guardian, setGuardian] = useState({ guardian_name: "", guardian_email: "", guardian_phone: "" });
  const save = useMutation({
    mutationFn: () => {
      const who = person.trim();
      const ref: MinorInput = /^\d+$/.test(who) ? { user_id: Number(who) } : { user_email: who };
      return communityStaffApi.recordMinor(makerspaceId, { ...ref, ...guardian, ...(declared ? { declared_under_age: true, date_of_birth: "" } : { date_of_birth: birth }) });
    },
    onSuccess: onSaved,
  });
  const ready = person.trim() && (declared || birth);
  return <Modal open title={t`Record a minor`} onClose={() => { if (!save.isPending) onClose(); }} footer={<div className="flex flex-wrap justify-end gap-2">
    <button type="button" className="desk-button" disabled={save.isPending} onClick={onClose}>{t`Cancel`}</button>
    <button type="button" className="desk-button-primary" disabled={!ready || save.isPending} onClick={() => save.mutate()}>{save.isPending ? t`Saving…` : t`Save`}</button>
  </div>}>
    <div className="grid gap-4">
      <Field label={t`Their e-mail or account number`}><input className="desk-input" autoComplete="off" value={person} onChange={(event) => setPerson(event.target.value)} /></Field>
      <Field label={t`Date of birth`} hint={t`Only the age is shown afterwards.`}>
        <input className="desk-input" type="date" disabled={declared} value={birth} onChange={(event) => setBirth(event.target.value)} /></Field>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" className="h-5 w-5 accent-accent" checked={declared} onChange={(event) => setDeclared(event.target.checked)} />
        {t`Record "under age" without a birth date`}</label>
      <fieldset className="grid gap-3"><legend className="text-sm font-semibold text-ink">{t`Guardian`}</legend>
        <Field label={t`Guardian's name`}><input className="desk-input" value={guardian.guardian_name} onChange={(event) => setGuardian({ ...guardian, guardian_name: event.target.value })} /></Field>
        <Field label={t`Guardian's e-mail`} hint={t`With an account under this e-mail they can sign the consent online.`}>
          <input className="desk-input" type="email" value={guardian.guardian_email} onChange={(event) => setGuardian({ ...guardian, guardian_email: event.target.value })} /></Field>
        <Field label={t`Guardian's phone`}><input className="desk-input" type="tel" value={guardian.guardian_phone} onChange={(event) => setGuardian({ ...guardian, guardian_phone: event.target.value })} /></Field>
      </fieldset>
      {save.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(save.error)}</p> : null}
    </div>
  </Modal>;
}

/** A guardian signed on paper or in person: record it against the CURRENT consent text. */
export function DeskConsentDialog({ makerspaceId, minor, onClose, onSaved }: {
  makerspaceId: number; minor: MinorProfile; onClose: () => void; onSaved: (consent: Consent) => void;
}) {
  const [name, setName] = useState(minor.guardian_name);
  const [accepted, setAccepted] = useState(false);
  const [key] = useState(operationId);
  const save = useMutation({ mutationFn: () => communityStaffApi.recordConsent(makerspaceId, minor.id, { signed_name: name.trim(), accepted, operation_id: key }), onSuccess: onSaved });
  return <Modal open title={t`Desk signature for ${minor.user_name}`} onClose={() => { if (!save.isPending) onClose(); }} footer={<div className="flex flex-wrap justify-end gap-2">
    <button type="button" className="desk-button" disabled={save.isPending} onClick={onClose}>{t`Cancel`}</button>
    <button type="button" className="desk-button-primary" disabled={!name.trim() || !accepted || save.isPending} onClick={() => save.mutate()}>{save.isPending ? t`Saving…` : t`Record signature`}</button>
  </div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`Use this when the guardian signed the current consent text on paper or in front of you.`}</p>
      <Field label={t`Guardian's full name as signed`}><input className="desk-input" value={name} onChange={(event) => setName(event.target.value)} /></Field>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" className="h-5 w-5 accent-accent" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
        {t`The guardian read and accepted the current consent text`}</label>
      {save.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(save.error)}</p> : null}
    </div>
  </Modal>;
}
