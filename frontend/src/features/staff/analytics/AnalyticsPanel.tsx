import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import { Callout, EmptyState, Skeleton } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { AnalyticsSettings } from "./AnalyticsSettings";
import { PublicFirebaseSettings } from "./PublicFirebaseSettings";
import { GrafanaViewer } from "./GrafanaViewer";
import { WebTelemetrySettings } from "./WebTelemetrySettings";
import { type AnalyticsScope, useAnalyticsEmbed, useAnalyticsSummary, usesGrafana, usesMetabase } from "./analyticsApi";

const errorText = (error: unknown, fallback: string) =>
  error instanceof StructuredApiError ? error.detail ?? error.message : fallback;

/** Lane L25 (#163B): the space's (or the platform's) Metabase dashboards, embedded through a
 *  server-signed URL that expires after ten minutes, and (decision 263) its Grafana
 *  dashboards when the chosen tool includes Grafana. Managers also see the connection. */
export function AnalyticsPanel({ scope }: { scope: AnalyticsScope }) {
  const summary = useAnalyticsSummary(scope);
  const [selected, setSelected] = useState<number | null>(null);
  const [managing, setManaging] = useState(false);
  const dashboards = summary.data?.dashboards ?? [];
  useEffect(() => {
    if (selected === null || !dashboards.some((entry) => entry.id === selected)) setSelected(dashboards[0]?.id ?? null);
  }, [dashboards, selected]);
  const metabase = usesMetabase(summary.data?.provider);
  const embed = useAnalyticsEmbed(scope, summary.data?.configured && metabase ? selected : null);
  const title = scope.kind === "platform" ? "Platform analytics" : "Analytics";

  if (summary.isLoading) return <section className="desk-panel p-5"><Skeleton className="h-40 w-full" /></section>;
  if (summary.error || !summary.data) {
    return <section className="desk-panel p-5"><Callout size="panel" tone="danger" lead="Analytics could not load."
      body={errorText(summary.error, "Try again in a moment.")} />{scope.kind === "platform" ? <PublicFirebaseSettings /> : <p>{t`Ask a platform administrator to configure Firebase web notifications.`}</p>}</section>;
  }
  const data = summary.data;
  return (
    <section className="desk-panel grid min-w-0 gap-4 p-5" aria-labelledby="analytics-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="title-panel" id="analytics-title">{title}</h1>
        {data.can_manage ? (
          <button className="desk-button" type="button" aria-expanded={managing} onClick={() => setManaging((open) => !open)}>
            {managing ? t`Close connection settings` : t`Connection settings`}
          </button>
        ) : null}
      </div>
      {managing && data.can_manage ? <><AnalyticsSettings scope={scope} /><WebTelemetrySettings key={scope.kind === "platform" ? "platform" : `space:${scope.makerspaceId}`} scope={scope} /></> : null}
      {scope.kind === "platform" ? <PublicFirebaseSettings /> : <p>{t`Ask a platform administrator to configure Firebase web notifications.`}</p>}
      {!metabase ? null : !data.configured || dashboards.length === 0 ? (
        <EmptyState message={data.can_manage
          ? t`Connect Metabase and list the dashboards to show here. Open Connection settings to start.`
          : t`No dashboards yet. Ask your Space Manager to connect Metabase.`} />
      ) : (
        <>
          {dashboards.length > 1 ? (
            <div className="flex flex-wrap gap-2" role="tablist" aria-label={t`Dashboards`}>
              {dashboards.map((entry) => (
                <button key={entry.id} type="button" role="tab" aria-selected={entry.id === selected}
                  className={entry.id === selected ? "desk-button-primary" : "desk-button"}
                  onClick={() => setSelected(entry.id)}>{entry.title}</button>
              ))}
            </div>
          ) : null}
          {embed.error ? (
            <Callout size="inline" tone="danger" lead="This dashboard could not open."
              body={errorText(embed.error, "Check the Metabase connection.")} />
          ) : !embed.data ? <Skeleton className="h-96 w-full" /> : (
            <div className="grid gap-2">
              <iframe className="h-[70vh] min-h-96 w-full rounded-xl border border-line bg-bg" src={embed.data.url}
                title={dashboards.find((entry) => entry.id === selected)?.title ?? t`Dashboard`}
                referrerPolicy="no-referrer" sandbox="allow-scripts allow-same-origin allow-popups allow-downloads" />
              <a className="text-sm text-muted underline" href={embed.data.url} target="_blank" rel="noreferrer noopener">
                {t`Open this dashboard in a new tab`}</a>
            </div>
          )}
        </>
      )}
      {usesGrafana(data.provider) ? <GrafanaViewer scope={scope} /> : null}
    </section>
  );
}
