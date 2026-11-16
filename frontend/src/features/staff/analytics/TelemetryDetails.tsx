import { t } from "@lingui/core/macro";
import type { WebTelemetryConfig } from "./telemetryApi";

export function TelemetryDetails({ value, onChange }: { value: WebTelemetryConfig; onChange: (next: WebTelemetryConfig) => void }) {
  const sentry = value.diagnostics.sentry, perf = value.diagnostics.firebase_performance;
  const firebaseFields = [
    ["api_key", t`API key`], ["auth_domain", t`Auth domain`], ["project_id", t`Project ID`],
    ["app_id", t`App ID`], ["messaging_sender_id", t`Messaging sender ID`],
    ["measurement_id", t`Measurement ID`], ["vapid_public_key", t`VAPID public key`],
  ] as const;
  return <div className="grid gap-3">
    <fieldset><legend>{t`Diagnostics`}</legend>
      <label><input type="checkbox" checked={sentry.enabled} onChange={e => onChange({ ...value, diagnostics: { ...value.diagnostics, sentry: { ...sentry, enabled: e.target.checked } } })} />{t`Sentry errors`}</label>
      <label>{t`Sentry DSN`}<input value={sentry.dsn} onChange={e => onChange({ ...value, diagnostics: { ...value.diagnostics, sentry: { ...sentry, dsn: e.target.value } } })} /></label>
      <label>{t`Sentry sample rate`}<input type="number" min="0" max="1" step="0.01" value={sentry.sample_rate} onChange={e => onChange({ ...value, diagnostics: { ...value.diagnostics, sentry: { ...sentry, sample_rate: Number(e.target.value) } } })} /></label>
      {sentry.enabled && sentry.sample_rate === 0 ? <p role="status">{t`Sentry is set to 0% sampling, so no error events will be sent.`}</p> : null}
      <label><input type="checkbox" checked={perf.enabled} onChange={e => onChange({ ...value, diagnostics: { ...value.diagnostics, firebase_performance: { ...perf, enabled: e.target.checked } } })} />{t`Firebase performance`}</label>
      <label>{t`Performance sample rate`}<input type="number" min="0" max="1" step="0.01" value={perf.sample_rate} onChange={e => onChange({ ...value, diagnostics: { ...value.diagnostics, firebase_performance: { ...perf, sample_rate: Number(e.target.value) } } })} /></label>
      {perf.enabled && perf.sample_rate === 0 ? <p role="status">{t`Performance is set to 0% sampling, so no performance events will be sent.`}</p> : null}
    </fieldset>
    <fieldset><legend>{t`Firebase web configuration`}</legend>
      {firebaseFields.map(([field, label]) => <label key={field}>{label}<input value={value.firebase[field]} onChange={e => onChange({ ...value, firebase: { ...value.firebase, [field]: e.target.value } })} /></label>)}
      <p>{t`Firebase Analytics requires a G- measurement ID. It is optional for Firebase Performance and web notifications.`}</p>
    </fieldset>
  </div>;
}
