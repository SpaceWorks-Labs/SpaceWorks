import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field, SettingsSection } from "../../components/ui";
import { CustomFormBuilder } from "../forms/CustomFormBuilder";
import { pageStickyActions } from "./stickyActions";
import type { BookableSpace, BookableSpacePayload } from "./bookingsApi";
import { BoxArt } from "../../components/BoxSpinner";

/** A resource grantee holding `edit_details` changes only the descriptive fields of a space. */
export function BookingDetailsEditor({ space, pending, onSubmit }: {
  space: BookableSpace; pending: boolean; onSubmit: (values: Partial<BookableSpacePayload>) => void;
}) {
  const [name, setName] = useState(space.name);
  const [description, setDescription] = useState(space.description);
  const [location, setLocation] = useState(space.location);
  const [capacity, setCapacity] = useState(space.capacity);
  const [kind, setKind] = useState(space.kind);
  const [form, setForm] = useState(space.custom_form);
  return <form className="grid gap-6" onSubmit={(event) => { event.preventDefault(); onSubmit({ name, description, location, capacity, kind, custom_form: form }); }}>
    <SettingsSection title={t`Space details`}>
      <div className="grid gap-4 py-5 sm:grid-cols-2">
        <Field label={t`Name`}><input className="desk-input w-full" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label={t`Type`}><select className="desk-input w-full" value={kind} onChange={(event) => setKind(event.target.value as BookableSpace["kind"])}>
          <option value="dev_room">{t`Development room`}</option><option value="bench">{t`Bench`}</option><option value="meeting">{t`Meeting room`}</option><option value="other">{t`Other`}</option>
          {space.kind === "machine" ? <option value="machine">{t`Machine time`}</option> : null}
        </select></Field>
        <Field label={t`Description`} className="sm:col-span-2"><textarea className="desk-input min-h-24 w-full" value={description} onChange={(event) => setDescription(event.target.value)} /></Field>
        <Field label={t`Location`}><input className="desk-input w-full" maxLength={255} value={location} onChange={(event) => setLocation(event.target.value)} /></Field>
        <Field label={t`Capacity`} hint={t`Use 0 when no capacity is published.`}><input className="desk-input w-full" type="number" min={0} value={capacity} onChange={(event) => setCapacity(Number(event.target.value))} /></Field>
      </div>
    </SettingsSection>
    <CustomFormBuilder value={form} onChange={setForm} disabled={pending || !space.is_active} />
    <div className={pageStickyActions}>
      <button className="desk-button-primary" type="submit" disabled={pending || !space.is_active}>{pending ? <><BoxArt size={16} mono />{t`Saving...`}</> : t`Save details`}</button>
    </div>
  </form>;
}
