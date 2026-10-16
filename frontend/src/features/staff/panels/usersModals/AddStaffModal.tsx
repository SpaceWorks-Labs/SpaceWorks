import { Field, Modal } from "../../../../components/ui";

import { GeneralError, ModalActions, validationErrors } from "./shared";
import { type StaffForm } from "./types";
import { RoleSetPicker, type RoleChoice } from "../RoleSetPicker";

export function AddStaffModal({
  open,
  form,
  makerspaceName,
  pending,
  error,
  roles,
  onChange,
  onClose,
  onSubmit,
}: {
  open: boolean;
  form: StaffForm;
  makerspaceName: string;
  pending: boolean;
  error: unknown;
  roles: RoleChoice[];
  onChange: (form: StaffForm) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  const errors = validationErrors(error);
  // Password is required: the API does not return an auto-generated one, so a
  // blank password would create an account nobody can sign into.
  const disabled = pending || !form.username.trim() || !form.password || !form.role_ids.length;
  return (
    <Modal open={open} onClose={onClose} title="Add staff" footer={<ModalActions pending={pending} disabled={disabled} onClose={onClose} onSubmit={onSubmit} />}>
      <form className="grid gap-3 text-sm" onSubmit={(event) => { event.preventDefault(); if (!disabled) onSubmit(); }}>
        <Field label="Username" error={errors.username}>
          <input className="desk-input w-full" value={form.username} onChange={(event) => onChange({ ...form, username: event.target.value })} />
        </Field>
        <Field label="Email" error={errors.email}>
          <input className="desk-input w-full" type="email" value={form.email} onChange={(event) => onChange({ ...form, email: event.target.value })} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="First name" error={errors.first_name}>
            <input className="desk-input w-full" value={form.first_name} onChange={(event) => onChange({ ...form, first_name: event.target.value })} />
          </Field>
          <Field label="Last name" error={errors.last_name}>
            <input className="desk-input w-full" value={form.last_name} onChange={(event) => onChange({ ...form, last_name: event.target.value })} />
          </Field>
        </div>
        <Field label="Password" hint="Required - share it with the new staff member." error={errors.password}>
          <input className="desk-input w-full" type="password" autoComplete="new-password" value={form.password} onChange={(event) => onChange({ ...form, password: event.target.value })} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <div><RoleSetPicker roles={roles} value={form.role_ids} disabled={pending} onChange={(role_ids) => onChange({ ...form, role_ids })} />{errors.role_ids ? <p role="alert" className="text-sm text-danger">{errors.role_ids}</p> : null}</div>
          <Field label="Makerspace">
            <div className="desk-input flex w-full items-center bg-surface text-muted">{makerspaceName}</div>
          </Field>
        </div>
        <GeneralError error={error} errors={errors} />
      </form>
    </Modal>
  );
}
