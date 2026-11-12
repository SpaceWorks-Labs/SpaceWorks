import { t } from "@lingui/core/macro";
import { useMemo, useEffect, useState } from "react";

import { Callout, EmptyState } from "../../../components/ui";
import { StructuredApiError, staffRequestBlob } from "../../../lib/api";
import type { AnalyticsScope } from "./analyticsApi";
import { type GrafanaDashboard, renderPath, useGrafanaEmbed, useGrafanaSummary } from "./grafanaApi";
import { LogoLoader } from "../../../components/LogoLoader";

const errorText = (error: unknown, fallback: string) =>
  error instanceof StructuredApiError ? error.detail ?? error.message : fallback;

const theme = (): "light" | "dark" =>
  typeof document !== "undefined" && document.documentElement.dataset.theme === "dark" ? "dark" : "light";

function PublicDashboard({ scope, dashboard }: { scope: AnalyticsScope; dashboard: GrafanaDashboard }) {
  const embed = useGrafanaEmbed(scope, dashboard.uid);
  if (embed.error) {
    return <Callout size="inline" tone="danger" lead="This dashboard could not open."
      body={errorText(embed.error, "Check the Grafana connection.")} />;
  }
  if (!embed.data) return <LogoLoader size={48} className="min-h-96 py-3" />;
  return (
    <div className="grid gap-2">
      <iframe className="h-[70vh] min-h-96 w-full rounded-xl border border-line bg-bg" src={embed.data.url}
        title={dashboard.title} referrerPolicy="no-referrer"
        sandbox="allow-scripts allow-same-origin allow-popups allow-downloads" />
      <a className="text-sm text-muted underline" href={embed.data.url} target="_blank" rel="noreferrer noopener">
        {t`Open this dashboard in a new tab`}</a>
    </div>
  );
}

/** A picture Grafana renders server-side with the saved token; the token never reaches the browser. */
function RenderedDashboard({ scope, dashboard }: { scope: AnalyticsScope; dashboard: GrafanaDashboard }) {
  const [version, setVersion] = useState(0);
  const [image, setImage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const path = renderPath(scope, dashboard.uid, theme());
  useEffect(() => {
    let alive = true;
    let url: string | null = null;
    setImage(null);
    setError(null);
    staffRequestBlob(path).then((blob) => {
      if (!alive) return;
      url = URL.createObjectURL(blob);
      setImage(url);
    }).catch((caught: unknown) => { if (alive) setError(caught); });
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [path, version]);
  return (
    <div className="grid gap-2">
      {error ? <Callout size="inline" tone="danger" lead="This dashboard could not be drawn."
        body={errorText(error, "Check the Grafana connection and its image renderer.")} />
        : image ? <img className="w-full rounded-xl border border-line bg-bg" src={image} alt={dashboard.title} />
          : <LogoLoader size={48} className="min-h-96 py-3" />}
      <div><button className="desk-button" type="button" onClick={() => setVersion((value) => value + 1)}>{t`Refresh image`}</button></div>
    </div>
  );
}

/** Decision 263: the space's (or the platform's) Grafana dashboards in the staff console. */
export function GrafanaViewer({ scope }: { scope: AnalyticsScope }) {
  const summary = useGrafanaSummary(scope, true);
  const [selected, setSelected] = useState<string | null>(null);
  const dashboards = useMemo(() => summary.data?.dashboards ?? [], [summary.data]);
  useEffect(() => {
    if (selected === null || !dashboards.some((entry) => entry.uid === selected)) setSelected(dashboards[0]?.uid ?? null);
  }, [dashboards, selected]);

  if (summary.isLoading) return <LogoLoader size={48} className="min-h-40 py-3" />;
  if (summary.error || !summary.data) {
    return <Callout size="inline" tone="danger" lead="Grafana dashboards could not load."
      body={errorText(summary.error, "Try again in a moment.")} />;
  }
  const current = dashboards.find((entry) => entry.uid === selected);
  return (
    <section className="grid gap-3" aria-label={t`Grafana dashboards`}>
      <h2 className="title-section">{t`Grafana`}</h2>
      {!summary.data.configured || dashboards.length === 0 || !current ? (
        <EmptyState message={summary.data.can_manage
          ? t`Connect Grafana and list the dashboards to show here. Open Connection settings to start.`
          : t`No Grafana dashboards yet. Ask your Space Manager to connect Grafana.`} />
      ) : (
        <>
          {dashboards.length > 1 ? (
            <div className="flex flex-wrap gap-2" role="tablist" aria-label={t`Grafana dashboards`}>
              {dashboards.map((entry) => (
                <button key={entry.uid} type="button" role="tab" aria-selected={entry.uid === selected}
                  className={entry.uid === selected ? "desk-button-primary" : "desk-button"}
                  onClick={() => setSelected(entry.uid)}>{entry.title}</button>
              ))}
            </div>
          ) : null}
          {current.mode === "render"
            ? <RenderedDashboard key={current.uid} scope={scope} dashboard={current} />
            : <PublicDashboard key={current.uid} scope={scope} dashboard={current} />}
        </>
      )}
    </section>
  );
}
