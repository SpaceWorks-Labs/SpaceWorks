import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { useCreateIpRule, type IpRule } from "./ipAccessApi";
import { fieldError, isoOrNull } from "./parityRequest";
import { BoxArt } from "../../../components/BoxSpinner";

const EMPTY = { cidr: "", action: "deny" as IpRule["action"], note: "", expires: "" };

/** Add one allow or deny rule; the server refuses a rule that would lock the caller out. */
export function IpRuleForm() {
  const create = useCreateIpRule();
  const [form, setForm] = useState(EMPTY);
  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) => setForm(current => ({ ...current, [key]: value }));
  const expiresInPast = Boolean(form.expires && (isoOrNull(form.expires) ?? "") <= new Date().toISOString());
  const valid = form.cidr.trim() && !expiresInPast;
  const cidrError = fieldError(create.error, "cidr");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || create.isPending) return;
    create.mutate({ cidr: form.cidr.trim(), action: form.action, note: form.note.trim(), expires_at: isoOrNull(form.expires) },
      { onSuccess: () => { toast(t`Rule added.`); setForm(EMPTY); } });
  };
  return <form className="grid gap-4 p-3" aria-label={t`New IP rule`} onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Address or range`} hint={t`One address (203.0.113.7) or a range (203.0.113.0/24).`} error={cidrError}>
        <input className="desk-input" value={form.cidr} maxLength={49} spellCheck={false} onChange={event => set("cidr", event.target.value)} />
      </Field>
      <Field label={t`Rule`}>
        <select className="desk-input" value={form.action} onChange={event => set("action", event.target.value as IpRule["action"])}>
          <option value="deny">{t`Deny`}</option>
          <option value="allow">{t`Allow`}</option>
        </select>
      </Field>
      <Field label={t`Note (optional)`}>
        <input className="desk-input" value={form.note} maxLength={200} onChange={event => set("note", event.target.value)} />
      </Field>
      <Field label={t`Expires (optional)`} hint={t`Leave empty to keep the rule until you delete it.`}
        error={expiresInPast ? "The expiry must be in the future." : undefined}>
        <input className="desk-input" type="datetime-local" value={form.expires} onChange={event => set("expires", event.target.value)} />
      </Field>
    </div>
    {create.error && !cidrError ? <p role="alert" className="text-sm text-danger">{actionErrorText(create.error)}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!valid || create.isPending}>
      {create.isPending ? <><BoxArt size={16} mono />{t`Adding…`}</> : t`Add rule`}
    </button>
  </form>;
}
