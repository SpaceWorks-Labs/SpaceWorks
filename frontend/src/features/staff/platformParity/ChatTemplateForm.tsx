import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { useSaveChatTemplate, type ChatTemplate, type ChatTemplateBody, type ChatTemplateSurface } from "./chatTemplatesApi";
import { fieldError } from "./parityRequest";

const EMPTY: ChatTemplateBody = { feature: "", event: "", text_body: "", is_active: true };
const FIELDS = ["feature", "event", "text_body"] as const;

/** Add a template, or change one when `row` is given. The server checks the event and renders the body. */
export function ChatTemplateForm({ spaceId, surface = "platform", row, onDone }: {
  spaceId: number; surface?: ChatTemplateSurface; row?: ChatTemplate; onDone?: () => void }) {
  const save = useSaveChatTemplate(spaceId, row?.id ?? null, surface);
  const [form, setForm] = useState<ChatTemplateBody>(row
    ? { feature: row.feature, event: row.event, text_body: row.text_body, is_active: row.is_active } : EMPTY);
  const set = <K extends keyof ChatTemplateBody>(key: K, value: ChatTemplateBody[K]) => setForm(current => ({ ...current, [key]: value }));
  const valid = FIELDS.every(name => form[name].trim());
  const general = save.error && !FIELDS.some(name => fieldError(save.error, name)) ? actionErrorText(save.error) : "";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || save.isPending) return;
    save.mutate({ ...form, feature: form.feature.trim(), event: form.event.trim() }, { onSuccess: () => {
      toast(row ? t`Template saved.` : t`Template added.`);
      if (!row) setForm(EMPTY);
      onDone?.();
    } });
  };
  return <form className="grid gap-4 p-3" aria-label={row ? t`Edit the ${row.event} template` : t`New chat template`} onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Feature`} hint={t`For example hardware_requests.`} error={fieldError(save.error, "feature")}>
        <input className="desk-input" value={form.feature} maxLength={32} spellCheck={false} onChange={event => set("feature", event.target.value)} />
      </Field>
      <Field label={t`Event`} error={fieldError(save.error, "event")}>
        <input className="desk-input" value={form.event} maxLength={64} spellCheck={false} onChange={event => set("event", event.target.value)} />
      </Field>
    </div>
    <Field label={t`Message`} hint={t`Django template syntax: {{ variable }} and {% if %} tags.`} error={fieldError(save.error, "text_body")}>
      <textarea className="desk-input min-h-32 font-mono" value={form.text_body} onChange={event => set("text_body", event.target.value)} />
    </Field>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={form.is_active} onChange={event => set("is_active", event.target.checked)} />{t`In use`}</label>
    {general ? <p role="alert" className="text-sm text-danger">{general}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!valid || save.isPending}>
        {save.isPending ? t`Saving…` : row ? t`Save template` : t`Add template`}
      </button>
      {row ? <button type="button" className="desk-button w-full sm:w-fit" disabled={save.isPending} onClick={onDone}>{t`Cancel`}</button> : null}
    </div>
  </form>;
}
