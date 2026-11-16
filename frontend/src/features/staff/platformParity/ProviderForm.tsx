import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { fieldError } from "./parityRequest";
import { ProviderSecretInput } from "./ProviderSecretInput";
import { useSaveProvider, type ProviderSettings } from "./providersApi";
import type { ProviderSpec } from "./providerSpecs";
import { BoxArt } from "../../../components/BoxSpinner";

type Draft = Record<string, string | boolean>;

/** Mount with a `key` of the saved row so a save starts a fresh draft (secrets always start empty). */
export function ProviderForm({ spec, saved }: { spec: ProviderSpec; saved: ProviderSettings }) {
  const save = useSaveProvider(spec.key);
  const [draft, setDraft] = useState<Draft>({ ...saved.values });
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [clears, setClears] = useState<Record<string, boolean>>({});
  const changed = Object.fromEntries(Object.entries(draft).filter(([name, value]) => saved.values[name] !== value));
  const secretBody = Object.fromEntries([
    ...Object.entries(secrets).filter(([name, value]) => value && !clears[name]),
    ...Object.entries(clears).filter(([, on]) => on).map(([name]) => [`clear_${name}`, true]),
  ]);
  const body = { ...changed, ...secretBody };
  const dirty = Object.keys(body).length > 0;
  const named = [...spec.fields.map(field => field.name), ...spec.secrets.map(secret => secret.name)];
  const general = save.error && !named.some(name => fieldError(save.error, name)) ? actionErrorText(save.error) : "";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!dirty || save.isPending) return;
    save.mutate(body, { onSuccess: () => toast(t`${spec.title} settings saved.`) });
  };
  return <form className="grid gap-4" aria-label={`${spec.title} settings`} onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      {spec.fields.map(field => field.kind === "toggle"
        ? <label key={field.name} className="flex min-h-11 items-center gap-3 text-sm text-ink sm:col-span-2">
          <input type="checkbox" checked={Boolean(draft[field.name])} onChange={event => setDraft({ ...draft, [field.name]: event.target.checked })} />
          {field.label}
        </label>
        : <Field key={field.name} label={field.label} hint={field.hint} error={fieldError(save.error, field.name)}>
          {field.kind === "select"
            ? <select className="desk-input" value={String(draft[field.name] ?? "")} onChange={event => setDraft({ ...draft, [field.name]: event.target.value })}>
              {(field.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}
            </select>
            : <input className="desk-input" value={String(draft[field.name] ?? "")} spellCheck={false} autoComplete="off"
              onChange={event => setDraft({ ...draft, [field.name]: event.target.value })} />}
        </Field>)}
    </div>
    {spec.secrets.map(secret => <ProviderSecretInput key={secret.name} field={secret}
      state={saved.secrets.find(row => row.name === secret.name)} value={secrets[secret.name] ?? ""} clear={Boolean(clears[secret.name])}
      error={fieldError(save.error, secret.name)} onValue={value => setSecrets({ ...secrets, [secret.name]: value })}
      onClear={on => setClears({ ...clears, [secret.name]: on })} />)}
    {fieldError(save.error, "non_field_errors") ? <p role="alert" className="text-sm text-danger">{fieldError(save.error, "non_field_errors")}</p> : null}
    {general ? <p role="alert" className="text-sm text-danger">{general}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!dirty || save.isPending}>
      {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save`}
    </button>
  </form>;
}
