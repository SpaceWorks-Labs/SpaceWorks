import { Callout, ErrorBlock, Field, Skeleton } from "../../components/ui";
import { ApiClientScopePicker } from "./ApiClientScopePicker";
import type { ApiClientCreateResponse, ApiClientScopeOption } from "./apiClientsApi";
import { splitOrigins } from "./apiClientsApi";
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
          <Field label="Client label">
            <input
              className="desk-input w-full"
              value={label}
              onChange={(event) => onLabelChange(event.target.value)}
            />
          </Field>
          <Field label="Allowed browser origins">
            <textarea
              className="desk-input min-h-24 w-full"
              placeholder="Allowed browser origins, one per line. Example: https://lab.example.com"
              value={origins}
              onChange={(event) => onOriginsChange(event.target.value)}
            />
          </Field>
          <div className="grid gap-2">
            <span className="font-semibold text-ink">What can it do?</span>
            <p className="text-xs text-muted">Choose the exact public API access this client needs.</p>
            {scopesLoading ? <Skeleton className="h-32 w-full" /> : null}
            {!scopesLoading && scopeOptions.length ? (
              <ApiClientScopePicker
                options={scopeOptions}
                selected={scopes}
                onChange={onScopesChange}
                disabled={isPending}
              />
            ) : null}
            {scopesError ? <ErrorBlock error={scopesError} resource="API scopes" onRetry={onRetryScopes} /> : null}
          </div>
        </div>
        <button
          className="desk-button-primary mt-3 w-full"
          disabled={!label.trim() || !splitOrigins(origins).length || !scopes.length || scopesLoading || !!scopesError || isPending}
          onClick={onSubmit}
        >
          {isPending ? "Creating…" : "Create API client"}
        </button>
        {error ? <p className="mt-2 text-sm text-danger">{error.message}</p> : null}
        {oneTimeSecret ? (
          <div className="mt-3 rounded-md border border-line bg-warn-soft p-3">
            <Callout size="inline" tone="warn" lead="Copy the secret now." body="It’s shown once." />
            <p className="mt-2 break-all rounded-md border border-line bg-bg p-2 code-text text-xs text-ink">
              {oneTimeSecret.client_secret}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                className="desk-button"
                type="button"
                onClick={() => void navigator.clipboard.writeText(oneTimeSecret.client_secret)}
              >
                Copy
              </button>
              <button className="desk-button-primary" type="button" onClick={onDismissSecret}>
                Done
              </button>
            </div>
          </div>
        ) : null}
      </article>
    );
  }
  return (
    <article className="grid gap-3">
      <div className="mt-3 grid gap-2">
        <Field label="Request label">
          <input
            className="desk-input w-full"
            value={label}
            onChange={(event) => onLabelChange(event.target.value)}
          />
        </Field>
        <Field label="Reason for API access">
          <textarea
            className="desk-input min-h-24 w-full"
            value={reason}
            onChange={(event) => onReasonChange(event.target.value)}
          />
        </Field>
        <Field label="Allowed browser origins">
          <textarea
            className="desk-input min-h-24 w-full"
            placeholder="Allowed browser origins, one per line. Example: https://lab.example.com"
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
        {isPending ? "Submitting…" : "Submit API access request"}
      </button>
      {submitted ? (
        <p className="mt-2 text-sm text-muted">
          Request submitted. A superadmin will review and share the key with you securely.
        </p>
      ) : null}
      {error ? <p className="mt-2 text-sm text-danger">{error.message}</p> : null}
    </article>
  );
}
