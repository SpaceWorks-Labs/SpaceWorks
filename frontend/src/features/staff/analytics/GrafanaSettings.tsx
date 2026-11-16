import { t } from "@lingui/core/macro";
import { useEffect, useState, type FormEvent } from "react";

import { Callout } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import type { AnalyticsScope } from "./analyticsApi";
import { GrafanaDashboardsEditor } from "./GrafanaDashboardsEditor";
import { GrafanaTokenCard } from "./GrafanaTokenCard";
import { GrafanaToolsCard } from "./GrafanaToolsCard";
import { type GrafanaDashboardEntry, useGrafanaConnection, useGrafanaMutations } from "./grafanaApi";
import { LogoLoader } from "../../../components/LogoLoader";

const message = (error: unknown) => error instanceof StructuredApiError ? error.message : t`Try again.`;

/** Space Manager (or the superadmin for the platform): the Grafana URL, organization,
 *  write-only token, dashboards to show, connection test and the provisioning bundle. */
export function GrafanaSettings({ scope }: { scope: AnalyticsScope }) {
  const connection = useGrafanaConnection(scope);
  const { update } = useGrafanaMutations(scope);
  const [url, setUrl] = useState("");
  const [orgId, setOrgId] = useState("1");
  const [dashboards, setDashboards] = useState<GrafanaDashboardEntry[]>([]);
  useEffect(() => {
    if (!connection.data) return;
    setUrl(connection.data.grafana_url);
    setOrgId(String(connection.data.org_id));
    setDashboards(connection.data.dashboards.map((row) => ({ ...row })));
  }, [connection.data]);

  if (connection.isLoading) return <LogoLoader size={48} className="min-h-40 py-3" />;
  if (connection.error || !connection.data) {
    return <Callout size="inline" tone="danger" lead="Grafana settings could not load." body={message(connection.error)} />;
  }
  const data = connection.data;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({
      grafana_url: url.trim(),
      org_id: Number(orgId) || 1,
      dashboards: dashboards.filter((row) => row.uid.trim()).map((row) => ({
        uid: row.uid.trim(), title: row.title.trim(), mode: row.mode,
        public_token: row.mode === "public" ? row.public_token.trim() : "",
      })),
    });
  };

  return (
    <section className="grid gap-5 rounded-xl border border-line p-4" aria-labelledby={`grafana-title-${scope.kind}`}>
      <h2 className="title-section" id={`grafana-title-${scope.kind}`}>{t`Grafana`}</h2>
      <form className="grid gap-3" onSubmit={submit} aria-label={t`Grafana connection`}>
        <label className="grid gap-1 text-sm font-semibold text-ink">
          {t`Grafana URL`}
          <span className="font-normal text-muted">{t`The address of your Grafana, for example https://grafana.example.org.`}</span>
          <input className="desk-input" type="url" placeholder="https://grafana.example.org" value={url}
            onChange={(event) => setUrl(event.target.value)} />
        </label>
        {scope.kind === "space" && !data.private_hosts_allowed ? (
          <p className="text-sm text-muted">{t`A Grafana on a private or local address works only after the operator allows it.`}</p>
        ) : null}
        <label className="grid gap-1 text-sm font-semibold text-ink">
          {t`Organization ID`}
          <span className="font-normal text-muted">{t`The Grafana organization that holds these dashboards. Usually 1.`}</span>
          <input className="desk-input w-28" inputMode="numeric" value={orgId}
            onChange={(event) => setOrgId(event.target.value.replace(/\D/g, ""))} />
        </label>
        <GrafanaDashboardsEditor rows={dashboards} onChange={setDashboards} />
        {update.error ? <Callout size="inline" tone="danger" lead="Not saved." body={message(update.error)} /> : null}
        <div><button className="desk-button-primary" type="submit" disabled={update.isPending}>{t`Save Grafana connection`}</button></div>
      </form>
      <GrafanaTokenCard scope={scope} connection={data} />
      <GrafanaToolsCard scope={scope} connection={data} />
      <p className="text-sm text-muted">
        {scope.kind === "platform"
          ? t`Grafana reads the platform views in schema ${data.database.schema} with the platform login.`
          : t`Grafana reads only this space's views in schema ${data.database.schema}, with this space's read-only login.`}
      </p>
    </section>
  );
}
