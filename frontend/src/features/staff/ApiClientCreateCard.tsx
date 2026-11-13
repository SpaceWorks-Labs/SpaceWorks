import { t } from "@lingui/core/macro";
import { ErrorBlock, Field } from "../../components/ui";
import { ApiClientScopePicker } from "./ApiClientScopePicker";
import { ApiClientSecretReveal } from "./ApiClientSecretReveal";
import type { ApiClientCreateResponse, ApiClientScopeOption, ApiClientType } from "./apiClientsApi";
import { splitOrigins } from "./apiClientsApi";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";
type Props = {
  canManageMakerspace: boolean;
  label: string;
  reason: string;
  origins: string;
  submitted: boolean;
  oneTimeSecret: ApiClientCreateResponse | null;
  isPending: boolean;
  error: Error | null;
  scopeOptions: ApiClientScopeOption[];
  scopes: string[];
  clientType?: ApiClientType;
  onClientTypeChange?: (value: ApiClientType) => void;
  scopesLoading: boolean;
  scopesError: Error | null;
  onRetryScopes?: () => void;
  onLabelChange: (value: string) => void;
  onReasonChange: (value: string) => void;
  onOriginsChange: (value: string) => void;
  onScopesChange: (value: string[]) => void;
  onSubmit: () => void;
  onDismissSecret: () => void;
};

const clientTypes = (): { value: ApiClientType; label: string; hint: string }[] => [
  { value: "server", label: t`Our own system`, hint: t`A script, an ERP or a backend that signs each request.` },
  { value: "peer", label: t`Another space`, hint: t`Their backend reads only your public catalogue, events and stats.` },
];

export function ApiClientCreateCard({
  canManageMakerspace,
  label,
  reason,
  origins,
  submitted,
  oneTimeSecret,
  isPending,
  error,
  scopeOptions,
  scopes,
  clientType = "server",
  onClientTypeChange,
  scopesLoading,
  scopesError,
  onRetryScopes,
  onLabelChange,
  onReasonChange,
  onOriginsChange,
  onScopesChange,
  onSubmit,
  onDismissSecret,
}: Props) {
  if (canManageMakerspace) {
    return (
      <article className="grid gap-3">
        <div className="mt-3 grid gap-2">
          <Field label={t`Client label`}>
            <input
              className="desk-input w-full"
              value={label}
              onChange={(event) => onLabelChange(event.target.value)}
            />
          </Field>
          <fieldset className="grid gap-2">
            <legend className="font-semibold text-ink">{t`Who will use it?`}</legend>
            {clientTypes().map((option) => (
              <label key={option.value} className="flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-panel p-3 has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
                <input type="radio" name="api-client-type" className="mt-1 h-4 w-4 accent-accent" value={option.value}
                  checked={clientType === option.value} disabled={isPending}
                  onChange={() => onClientTypeChange?.(option.value)} />
                <span className="grid gap-0.5"><span className="font-semibold text-ink">{option.label}</span>
                  <span className="text-xs text-muted">{option.hint}</span></span>
              </label>
            ))}
          </fieldset>
          <Field label={clientType === "peer" ? t`The other space's web address` : t`Allowed browser origins`}>
            <textarea
              className="desk-input min-h-24 w-full"
              placeholder={t`One per line. Example: https://lab.example.com`}
              value={origins}
              onChange={(event) => onOriginsChange(event.target.value)}
            />
          </Field>
          <div className="grid gap-2">
            <span className="font-semibold text-ink">{t`What can it do?`}</span>
            <p className="text-xs text-muted">{t`Choose the exact public API access this client needs.`}</p>
            {scopesLoading ? <LogoLoader size={48} className="min-h-32 py-3" /> : null}
            {!scopesLoading && scopeOptions.length ? (
              <ApiClientScopePicker
                options={scopeOptions}
                selected={scopes}
                onChange={onScopesChange}
                disabled={isPending}
              />
            ) : null}
            {scopesError ? <ErrorBlock error={scopesError} resource={t`API scopes`} onRetry={onRetryScopes} /> : null}
          </div>
        </div>
        <button
          className="desk-button-primary mt-3 w-full"
          disabled={!label.trim() || !splitOrigins(origins).length || !scopes.length || scopesLoading || !!scopesError || isPending}
          onClick={onSubmit}
        >
          {isPending ? <><BoxArt size={16} mono />{t`Creating…`}</> : t`Create API client`}
        </button>
        {error ? <p className="mt-2 text-sm text-danger">{error.message}</p> : null}
        {oneTimeSecret ? <ApiClientSecretReveal secret={oneTimeSecret.client_secret} onDismiss={onDismissSecret} /> : null}
      </article>
    );
  }
  return (
    <article className="grid gap-3">
      <div className="mt-3 grid gap-2">
        <Field label={t`Request label`}>
          <input
            className="desk-input w-full"
            value={label}
            onChange={(event) => onLabelChange(event.target.value)}
          />
        </Field>
        <Field label={t`Reason for API access`}>
          <textarea
            className="desk-input min-h-24 w-full"
            value={reason}
            onChange={(event) => onReasonChange(event.target.value)}
          />
        </Field>
        <Field label={t`Allowed browser origins`}>
          <textarea
            className="desk-input min-h-24 w-full"
            placeholder={t`Allowed browser origins, one per line. Example: https://lab.example.com`}
            value={origins}
            onChange={(event) => onOriginsChange(event.target.value)}
          />
        </Field>
      </div>
      <button
        className="desk-button-primary mt-3 w-full"
        disabled={!label.trim() || !reason.trim() || !splitOrigins(origins).length || isPending}
        onClick={onSubmit}
      >
        {isPending ? <><BoxArt size={16} mono />{t`Submitting…`}</> : t`Submit API access request`}
      </button>
      {submitted ? (
        <p className="mt-2 text-sm text-muted">
          {t`Request submitted. A superadmin will review and share the key with you securely.`}</p>
      ) : null}
      {error ? <p className="mt-2 text-sm text-danger">{error.message}</p> : null}
    </article>
  );
}
