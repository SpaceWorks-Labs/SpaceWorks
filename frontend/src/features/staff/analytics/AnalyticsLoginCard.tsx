import { useState } from "react";

import { Callout, ConfirmDialog } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { type AnalyticsConnection, type AnalyticsCredentials, type AnalyticsScope, useAnalyticsLogin } from "./analyticsApi";

const failure = (error: unknown) => error instanceof StructuredApiError && error.code === "analytics_not_available"
  ? "Analytics logins are not available on this hosting."
  : error instanceof StructuredApiError ? error.detail ?? error.message : "Could not create the login.";

/** The read-only database login: create, rotate (password shown once) and revoke. */
export function AnalyticsLoginCard({ scope, connection }: { scope: AnalyticsScope; connection: AnalyticsConnection }) {
  const { create, rotate, revoke } = useAnalyticsLogin(scope);
  const [shown, setShown] = useState<AnalyticsCredentials | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const login = connection.login;
  const pending = create.isPending || rotate.isPending || revoke.isPending;
  const error = create.error ?? rotate.error ?? revoke.error;
  const reveal = (credentials: AnalyticsCredentials) => setShown(credentials);

  if (!connection.available) {
    return <Callout size="inline" tone="warn" lead="Not available on this hosting."
      body="The database owner cannot create logins here, so Metabase cannot connect directly. Dashboards you already list still embed." />;
  }
  return (
    <div className="grid gap-3">
      {login.role ? (
        <dl className="grid gap-1 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted">Login</dt><dd className="code-text break-all">{login.role}</dd>
          <dt className="text-muted">Database</dt>
          <dd className="code-text break-all">{connection.database.host}:{connection.database.port} / {connection.database.database}</dd>
          <dt className="text-muted">Schema</dt><dd className="code-text">{connection.database.schema}</dd>
          {!login.exists ? <><dt className="text-muted">State</dt><dd>Missing from the database: rotate to recreate it.</dd></> : null}
        </dl>
      ) : <p className="text-sm text-muted">No login yet. Metabase connects to the curated views with a read-only login of its own.</p>}
      {shown ? (
        <div className="rounded-md border border-line bg-warn-soft p-3">
          <Callout size="inline" tone="warn" lead="Copy the password now." body="It is shown once. Paste these into Metabase as a PostgreSQL database." />
          <p className="mt-2 break-all rounded-md border border-line bg-bg p-2 code-text text-xs text-ink">
            user {shown.role} · password {shown.password} · schema {shown.schema}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="desk-button" type="button" onClick={() => void navigator.clipboard.writeText(shown.password)}>Copy password</button>
            <button className="desk-button-primary" type="button" onClick={() => setShown(null)}>Done</button>
          </div>
        </div>
      ) : null}
      {error ? <Callout size="inline" tone="danger" lead="Not done." body={failure(error)} /> : null}
      <div className="flex flex-wrap gap-2">
        {login.role ? (
          <>
            <button className="desk-button" type="button" disabled={pending} onClick={() => rotate.mutate(undefined, { onSuccess: reveal })}>Rotate password</button>
            <button className="desk-button" type="button" disabled={pending} onClick={() => setConfirmRevoke(true)}>Revoke login</button>
          </>
        ) : (
          <button className="desk-button-primary" type="button" disabled={pending} onClick={() => create.mutate(undefined, { onSuccess: reveal })}>Create login</button>
        )}
      </div>
      <ConfirmDialog open={confirmRevoke} title="Revoke the analytics login?" tone="danger" pending={revoke.isPending}
        message="Metabase loses access straight away. You can create a new login later."
        confirmLabel="Revoke" onCancel={() => setConfirmRevoke(false)}
        onConfirm={() => revoke.mutate(undefined, { onSettled: () => setConfirmRevoke(false) })} />
    </div>
  );
}
