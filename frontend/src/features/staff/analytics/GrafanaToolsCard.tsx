import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Callout } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import type { AnalyticsScope } from "./analyticsApi";
import { downloadGrafanaBundle, type GrafanaConnection, useGrafanaMutations } from "./grafanaApi";
import { BoxArt } from "../../../components/BoxSpinner";

const message = (error: unknown) => error instanceof StructuredApiError ? error.detail ?? error.message : t`Try again.`;

/** Test the saved connection and download the provisioning bundle. */
export function GrafanaToolsCard({ scope, connection }: { scope: AnalyticsScope; connection: GrafanaConnection }) {
  const { test } = useGrafanaMutations(scope);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<unknown>(null);
  const download = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadGrafanaBundle(scope);
    } catch (error) {
      setDownloadError(error);
    } finally {
      setDownloading(false);
    }
  };
  const result = test.data;
  return (
    <div className="grid gap-3">
      <div className="grid gap-2">
        <div><button className="desk-button" type="button" disabled={test.isPending || !connection.grafana_url}
          onClick={() => test.mutate()}>{test.isPending ? <><BoxArt size={16} mono />{t`Testing…`}</> : t`Test connection`}</button></div>
        <p className="text-sm text-muted">{t`Checks that Grafana answers and that the saved token can list dashboards.`}</p>
        {test.error ? <Callout size="inline" tone="danger" lead="Test failed." body={message(test.error)} /> : null}
        {result ? (
          <div role="status" className="grid gap-1 text-sm">
            <p className="font-semibold text-ink">{result.ok ? t`Grafana is reachable.` : t`Grafana is not working yet.`}
              {result.version ? ` ${t`Version ${result.version}.`}` : ""}
              {result.dashboards_found !== null ? ` ${t`Dashboards found: ${result.dashboards_found}.`}` : ""}</p>
            <ul className="grid gap-1">
              {result.checks.map((check) => (
                <li key={check.name}>
                  {check.name === "health" ? t`Health` : t`Dashboard search`}: {check.ok ? t`OK` : t`Error`}
                  {check.detail ? ` — ${check.detail}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <div className="grid gap-2">
        <div><button className="desk-button" type="button" disabled={downloading} onClick={() => void download()}>
          {t`Download provisioning bundle`}</button></div>
        <p className="text-sm text-muted">{t`A Grafana data source and starter dashboards for the areas switched on. The database password is never included: paste the one shown when the login is created or rotated.`}</p>
        {downloadError ? <Callout size="inline" tone="danger" lead="Download failed." body={message(downloadError)} /> : null}
      </div>
    </div>
  );
}
