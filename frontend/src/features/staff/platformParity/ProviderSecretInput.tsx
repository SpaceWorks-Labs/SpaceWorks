import { Field, RelativeTime, StatusPill } from "../../../components/ui";
import type { SecretState } from "./providersApi";
import type { SecretField } from "./providerSpecs";

type Props = { field: SecretField; state?: SecretState; value: string; clear: boolean; error?: string;
  onValue: (value: string) => void; onClear: (clear: boolean) => void };

/** A write-only secret: the server only ever says whether it is set, so the input starts empty. */
export function ProviderSecretInput({ field, state, value, clear, error, onValue, onClear }: Props) {
  const stamp = state?.last_changed;
  const hint = state?.set ? "Leave blank to keep the saved value." : field.hint;
  const common = { className: "desk-input font-mono", value, autoComplete: "off", spellCheck: false, disabled: clear,
    onChange: (event: { target: { value: string } }) => onValue(event.target.value) };
  return <div className="grid gap-2">
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
      <StatusPill label={state?.set ? "Set" : "Not set"} tone={state?.set ? "success" : "neutral"} />
      {stamp?.at ? <span>changed <RelativeTime date={stamp.at} exact />{stamp.by ? ` by ${stamp.by}` : ""}</span> : null}
    </div>
    <Field label={field.label} hint={hint} error={error}>
      {field.multiline ? <textarea {...common} className="desk-input min-h-28 font-mono" /> : <input {...common} type="password" />}
    </Field>
    {state?.set ? <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={clear} onChange={event => onClear(event.target.checked)} />Remove the saved {field.label.toLowerCase()}
    </label> : null}
  </div>;
}
