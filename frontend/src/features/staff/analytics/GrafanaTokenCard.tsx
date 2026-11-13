import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";

import { Callout, ConfirmDialog } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import type { AnalyticsScope } from "./analyticsApi";
import { type GrafanaConnection, useGrafanaMutations } from "./grafanaApi";

const message = (error: unknown) => error instanceof StructuredApiError ? error.detail ?? error.message : t`Try again.`;

/** The Grafana service-account token: write-only. It is never shown or prefilled. */
export function GrafanaTokenCard({ scope, connection }: { scope: AnalyticsScope; connection: GrafanaConnection }) {
  const { setToken, revokeToken } = useGrafanaMutations(scope);
  const [token, setDraft] = useState("");
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (token.trim()) setToken.mutate(token.trim(), { onSuccess: () => setDraft("") });
  };
  const error = setToken.error ?? revokeToken.error;
  return (
    <form className="grid gap-2" onSubmit={submit} aria-label={t`Grafana service-account token`}>
      <label className="grid gap-1 text-sm font-semibold text-ink">
        {t`Service-account token`}
        <span className="font-normal text-muted">
          {connection.token_set ? t`A token is saved. Enter a new one to replace it.` : t`In Grafana: Administration, Service accounts, add a Viewer account, then add a token.`}
        </span>
        <input className="desk-input" type="password" autoComplete="off" value={token}
          onChange={(event) => setDraft(event.target.value)} />
      </label>
      {error ? <Callout size="inline" tone="danger" lead="Not done." body={message(error)} /> : null}
      <div className="flex flex-wrap gap-2">
        <button className="desk-button-primary" type="submit" disabled={!token.trim() || setToken.isPending}>
          {connection.token_set ? t`Replace token` : t`Save token`}
        </button>
        {connection.token_set ? (
          <button className="desk-button" type="button" disabled={revokeToken.isPending} onClick={() => setConfirmRevoke(true)}>
            {t`Remove token`}</button>
        ) : null}
      </div>
      <ConfirmDialog open={confirmRevoke} title={t`Remove the Grafana token?`} tone="danger" pending={revokeToken.isPending}
        message={t`SpaceWorks stops reaching Grafana with it. Also delete the token in Grafana.`}
        confirmLabel={t`Remove`} onCancel={() => setConfirmRevoke(false)}
        onConfirm={() => revokeToken.mutate(undefined, { onSettled: () => setConfirmRevoke(false) })} />
    </form>
  );
}
