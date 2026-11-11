import { t } from "@lingui/core/macro";

import type { GrafanaDashboardEntry, GrafanaMode } from "./grafanaApi";

const blank = (): GrafanaDashboardEntry => ({ uid: "", title: "", mode: "public", public_token: "" });

/** The Grafana dashboards to list in the console: uid, title, how to show it, and the
 *  public dashboard access token when shown as a public dashboard. */
export function GrafanaDashboardsEditor({ rows, onChange }: {
  rows: GrafanaDashboardEntry[]; onChange: (rows: GrafanaDashboardEntry[]) => void;
}) {
  const setRow = (index: number, change: Partial<GrafanaDashboardEntry>) =>
    onChange(rows.map((row, at) => (at === index ? { ...row, ...change } : row)));
  return (
    <fieldset className="grid gap-2">
      <legend className="text-sm font-semibold text-ink">{t`Grafana dashboards to show`}</legend>
      <p className="text-sm text-muted">{t`The UID is the part after /d/ in the dashboard's address. Public shows a Grafana public dashboard; Image shows a picture Grafana renders.`}</p>
      {rows.map((row, index) => (
        <div className="flex flex-wrap items-end gap-2" key={index}>
          <label className="grid gap-1 text-sm">{t`UID`}
            <input className="desk-input w-40" value={row.uid} maxLength={40} aria-label={t`Grafana dashboard ${index + 1} UID`}
              onChange={(event) => setRow(index, { uid: event.target.value })} />
          </label>
          <label className="grid min-w-48 flex-1 gap-1 text-sm">{t`Title`}
            <input className="desk-input" value={row.title} maxLength={120} aria-label={t`Grafana dashboard ${index + 1} title`}
              onChange={(event) => setRow(index, { title: event.target.value })} />
          </label>
          <label className="grid gap-1 text-sm">{t`Show as`}
            <select className="desk-input" value={row.mode} aria-label={t`Grafana dashboard ${index + 1} display`}
              onChange={(event) => setRow(index, { mode: event.target.value as GrafanaMode })}>
              <option value="public">{t`Public dashboard`}</option>
              <option value="render">{t`Image`}</option>
            </select>
          </label>
          {row.mode === "public" ? (
            <label className="grid min-w-48 flex-1 gap-1 text-sm">{t`Public access token`}
              <input className="desk-input" value={row.public_token} maxLength={64} autoComplete="off"
                aria-label={t`Grafana dashboard ${index + 1} public access token`}
                onChange={(event) => setRow(index, { public_token: event.target.value.trim() })} />
            </label>
          ) : null}
          <button className="desk-button" type="button" onClick={() => onChange(rows.filter((_, at) => at !== index))}>{t`Remove`}</button>
        </div>
      ))}
      <p className="text-sm text-muted">{t`The public access token is the last part of the link Grafana gives when you share a dashboard publicly.`}</p>
      <div><button className="desk-button" type="button" onClick={() => onChange([...rows, blank()])}>{t`Add Grafana dashboard`}</button></div>
    </fieldset>
  );
}
