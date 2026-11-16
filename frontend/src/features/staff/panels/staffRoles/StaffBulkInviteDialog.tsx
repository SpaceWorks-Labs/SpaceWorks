import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErrorText, Field, Modal } from "../../../../components/ui";
import { StructuredApiError, staffRequest } from "../../../../lib/api";
import { StaffRoleFields, validRoleSet, type RoleDraft } from "./StaffRoleEditor";
import { needsMachineScope, staffRoleErrorText, type StaffRolesPolicy } from "./staffRolesApi";
import { BoxArt } from "../../../../components/BoxSpinner";

const LIMIT = 50;
type Row = { email: string; role: string };
type Result = { invited: number; invitation_ids: number[]; delivery: string[] };

/** Emails pasted one per line (or separated by commas/semicolons), deduplicated, at most 50. */
export function parseEmails(text: string) {
  const seen = new Set<string>();
  return text.split(/[\s,;]+/).map(value => value.trim()).filter(value => {
    const key = value.toLowerCase();
    if (!value || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Decision 248 (C1b): invite up to 50 people by email at once. Every row gets the default role set
 * unless it picks its own role; the server treats the batch as all-or-nothing and names the failing
 * row (its position) on a 409, so nobody is half-invited.
 */
export function StaffBulkInviteDialog({ space, policy, onClose, onDone }: {
  space: number; policy: StaffRolesPolicy; onClose: () => void; onDone: (text: string) => void;
}) {
  const [paste, setPaste] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [draft, setDraft] = useState<RoleDraft>({ roles: [], machine_type_ids: [], machine_ids: [] });
  const invite = useMutation({
    mutationFn: () => staffRequest<Result>(`/admin/makerspaces/${space}/staff-roles/bulk-invite/`, { method: "POST", body: JSON.stringify({
      invites: rows.map(row => {
        const roles = row.role ? [row.role] : draft.roles;
        const scoped = needsMachineScope(policy, roles);
        return { email: row.email.trim(), roles, machine_type_ids: scoped ? draft.machine_type_ids : [], machine_ids: scoped ? draft.machine_ids : [] };
      }) }) }),
    onSuccess: result => {
      const failed = result.delivery.filter(status => status !== "sent").length;
      onDone(failed ? t`${result.invited} invitations created. ${failed} emails could not be sent; resend them from Invitations.`
        : t`${result.invited} invitations sent.`);
    },
  });
  const addPasted = () => {
    const next = parseEmails(paste).filter(email => !rows.some(row => row.email.toLowerCase() === email.toLowerCase()));
    setRows(current => [...current, ...next.map(email => ({ email, role: "" }))].slice(0, LIMIT));
    setPaste("");
  };
  const usesDefault = rows.some(row => !row.role);
  const ready = rows.length > 0 && rows.every(row => row.email.includes("@")) && (!usesDefault || validRoleSet(policy, draft.roles));
  const failedText = (() => {
    const error = invite.error;
    if (!(error instanceof StructuredApiError) || error.status !== 409 || typeof error.body.failed_id !== "number") return error ? staffRoleErrorText(error) : "";
    const index = error.body.failed_id;
    const cause = typeof error.body.cause === "string" ? error.body.cause : staffRoleErrorText(error);
    return t`Nobody was invited. Row ${index + 1} (${rows[index]?.email ?? "?"}) could not be invited: ${cause}`;
  })();
  return <Modal open size="xl" title={t`Invite several staff`} onClose={() => { if (!invite.isPending) onClose(); }}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (ready && !invite.isPending) invite.mutate(); }}>
      <fieldset disabled={invite.isPending} className="grid min-w-0 gap-4">
        <legend className="sr-only">{t`People to invite`}</legend>
        <Field label={t`Paste email addresses`} hint={t`One per line, or separated by commas. Up to ${LIMIT} people.`}>
          <textarea className="desk-input min-h-24 w-full" value={paste} onChange={event => setPaste(event.target.value)} />
        </Field>
        <button type="button" className="desk-button min-h-11 w-fit" disabled={!paste.trim() || rows.length >= LIMIT} onClick={addPasted}>{t`Add to the list`}</button>
        {rows.length ? <ul className="grid gap-2" aria-label={t`People to invite`}>{rows.map((row, index) => <li key={index}
          className="grid gap-2 rounded-lg border border-line p-2 sm:grid-cols-[1fr_14rem_auto] sm:items-end">
          <Field label={t`Email ${index + 1}`}><input className="desk-input w-full" type="email" required maxLength={254} value={row.email}
            onChange={event => setRows(current => current.map((item, at) => at === index ? { ...item, email: event.target.value } : item))} /></Field>
          <Field label={t`Role`}><select className="desk-input w-full" value={row.role}
            onChange={event => setRows(current => current.map((item, at) => at === index ? { ...item, role: event.target.value } : item))}>
            <option value="">{t`Default roles (below)`}</option>
            {policy.grantable_roles.map(role => <option key={role.slug} value={role.slug}>{role.name}</option>)}
          </select></Field>
          <button type="button" className="desk-button min-h-11" onClick={() => setRows(current => current.filter((_, at) => at !== index))}>{t`Remove`}</button>
        </li>)}</ul> : <p className="text-sm text-muted">{t`No one on the list yet.`}</p>}
        <p role="status" className="text-sm text-muted">{t`${rows.length} of ${LIMIT}`}</p>
        <fieldset className="grid gap-2 rounded-lg border border-line p-3">
          <legend className="px-1 text-sm font-semibold">{t`Default roles`}</legend>
          <StaffRoleFields policy={policy} draft={draft} onChange={setDraft} />
        </fieldset>
      </fieldset>
      {failedText ? <ErrorText message={failedText} /> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button" disabled={invite.isPending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-primary" disabled={invite.isPending || !ready}>
          {invite.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send ${rows.length} invitations`}</button>
      </div>
    </form>
  </Modal>;
}
