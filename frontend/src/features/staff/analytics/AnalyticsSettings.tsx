import { useEffect, useState, type FormEvent } from "react";

import { Callout, Skeleton } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { AnalyticsLoginCard } from "./AnalyticsLoginCard";
import {
  type AnalyticsDashboard, type AnalyticsScope, useAnalyticsConnection, useUpdateAnalyticsConnection,
} from "./analyticsApi";

type DashboardDraft = { id: string; title: string };
const toDraft = (rows: AnalyticsDashboard[]): DashboardDraft[] => rows.map((row) => ({ id: String(row.id), title: row.title }));

/** Space Manager (or superadmin): the Metabase URL, the write-only embedding secret, the
 *  dashboards to list, the member-details switch and the read-only database login. */
export function AnalyticsSettings({ scope }: { scope: AnalyticsScope }) {
  const connection = useAnalyticsConnection(scope, true);
  const update = useUpdateAnalyticsConnection(scope);
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [dashboards, setDashboards] = useState<DashboardDraft[]>([]);
  const [details, setDetails] = useState(false);
  useEffect(() => {
    if (!connection.data) return;
    setUrl(connection.data.metabase_url);
    setDashboards(toDraft(connection.data.dashboards));
    setDetails(Boolean(connection.data.show_member_details));
  }, [connection.data]);

  if (connection.isLoading) return <Skeleton className="h-40 w-full" />;
  if (connection.error || !connection.data) {
    return <Callout size="inline" tone="danger" lead="Connection settings could not load."
      body={connection.error instanceof StructuredApiError ? connection.error.message : "Try again."} />;
  }
  const data = connection.data;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({
      metabase_url: url,
      dashboards: dashboards.filter((row) => row.id.trim()).map((row) => ({ id: Number(row.id), title: row.title.trim() })),
      ...(secret ? { embed_secret: secret } : {}),
      ...(scope.kind === "space" ? { show_member_details: details } : {}),
    }, { onSuccess: () => setSecret("") });
  };
  const setRow = (index: number, change: Partial<DashboardDraft>) =>
    setDashboards((rows) => rows.map((row, at) => (at === index ? { ...row, ...change } : row)));

  return (
    <div className="grid gap-5 rounded-xl border border-line p-4">
      <form className="grid gap-3" onSubmit={submit} aria-label="Metabase connection">
        <label className="grid gap-1 text-sm font-semibold text-ink">
          Metabase site URL
          <input className="desk-input" type="url" placeholder="https://metabase.example.org" value={url}
            onChange={(event) => setUrl(event.target.value)} />
        </label>
        <label className="grid gap-1 text-sm font-semibold text-ink">
          Embedding secret key {data.embed_secret_set ? <span className="font-normal text-muted">(set; leave blank to keep)</span> : null}
          <input className="desk-input" type="password" autoComplete="off" value={secret}
            onChange={(event) => setSecret(event.target.value)} />
        </label>
        <fieldset className="grid gap-2">
          <legend className="text-sm font-semibold text-ink">Dashboards to show</legend>
          {dashboards.map((row, index) => (
            <div className="flex flex-wrap items-end gap-2" key={index}>
              <label className="grid gap-1 text-sm">Number
                <input className="desk-input w-28" inputMode="numeric" value={row.id} aria-label={`Dashboard ${index + 1} number`}
                  onChange={(event) => setRow(index, { id: event.target.value.replace(/\D/g, "") })} />
              </label>
              <label className="grid min-w-48 flex-1 gap-1 text-sm">Title
                <input className="desk-input" value={row.title} maxLength={120} aria-label={`Dashboard ${index + 1} title`}
                  onChange={(event) => setRow(index, { title: event.target.value })} />
              </label>
              <button className="desk-button" type="button" onClick={() => setDashboards((rows) => rows.filter((_, at) => at !== index))}>Remove</button>
            </div>
          ))}
          <div><button className="desk-button" type="button" onClick={() => setDashboards((rows) => [...rows, { id: "", title: "" }])}>Add dashboard</button></div>
        </fieldset>
        {scope.kind === "space" ? (
          <label className="flex items-start gap-2 text-sm text-ink">
            <input type="checkbox" checked={details} onChange={(event) => setDetails(event.target.checked)} />
            <span>Show member names and emails in the analytics views. Off keeps them masked; every other view only ever names a member by number.</span>
          </label>
        ) : <p className="text-sm text-muted">The platform views cover every space and never include member names or emails.</p>}
        {update.error ? <Callout size="inline" tone="danger" lead="Not saved."
          body={update.error instanceof StructuredApiError ? update.error.message : "Try again."} /> : null}
        <div><button className="desk-button-primary" type="submit" disabled={update.isPending}>Save connection</button></div>
      </form>
      <section className="grid gap-2" aria-label="Database login">
        <h2 className="title-section">Read-only database login</h2>
        <p className="text-sm text-muted">Views version {data.views_version}. Metabase sees only the curated views in schema {data.database.schema}.</p>
        <AnalyticsLoginCard scope={scope} connection={data} />
      </section>
    </div>
  );
}
