import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { fieldError } from "./parityRequest";
import { useTestProvider, type ProviderKey } from "./providersApi";
import { BoxArt } from "../../../components/BoxSpinner";

/** "Send test" (SMS: one text to a number you type) or "Check credentials" (push, WhatsApp). */
export function ProviderTestAction({ provider, kind }: { provider: ProviderKey; kind: "send" | "check" }) {
  const test = useTestProvider(provider);
  const [to, setTo] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (test.isPending || (kind === "send" && !to.trim())) return;
    test.mutate(kind === "send" ? { to: to.trim() } : {});
  };
  const ok = test.data ? (kind === "send" ? "Test message sent. Check the phone."
    : `Credentials work${test.data.checked?.length ? ` (${test.data.checked.join(", ")})` : ""}.`) : "";
  const failed = test.error && !fieldError(test.error, "to") ? actionErrorText(test.error) : "";
  return <form className="grid gap-3 rounded-xl border border-line bg-panel p-3" aria-label={t`Test ${provider}`} onSubmit={submit} noValidate>
    {kind === "send" ? <Field label={t`Send a test text to`} hint={t`Uses the saved sign-in number. Your provider charges for it.`}
      error={fieldError(test.error, "to")}>
      <input className="desk-input sm:max-w-72" type="tel" inputMode="tel" autoComplete="off" value={to} onChange={event => setTo(event.target.value)} />
    </Field> : <p className="text-sm text-muted">{t`Checks the saved credentials with the provider. Nothing is sent to anyone.`}</p>}
    <div aria-live="polite" className="grid gap-2">
      {ok ? <p className="text-sm text-success-ink">{ok}</p> : null}
      {failed ? <p role="alert" className="text-sm text-danger">{failed}</p> : null}
    </div>
    <button type="submit" className="desk-button w-full sm:w-fit" disabled={test.isPending || (kind === "send" && !to.trim())}>
      {test.isPending ? <><BoxArt size={16} mono />{t`Testing…`}</> : kind === "send" ? t`Send test` : t`Check credentials`}
    </button>
  </form>;
}
