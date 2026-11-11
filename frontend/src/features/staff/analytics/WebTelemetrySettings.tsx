import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { StructuredApiError } from "../../../lib/api";
import type { AnalyticsScope } from "./analyticsApi";
import { useWebTelemetry, type WebTelemetryConfig } from "./telemetryApi";
import { TelemetryDetails } from "./TelemetryDetails";
import { TelemetryProviderHelp } from "./TelemetryProviderHelp";

export function WebTelemetrySettings({ scope }: { scope: AnalyticsScope }) {
  const { query, save } = useWebTelemetry(scope);
  const [draft, setDraft] = useState<WebTelemetryConfig | null>(null);
  useEffect(() => { if (query.data) setDraft(structuredClone(query.data.config)); }, [query.data]);
  if (query.isPending) return <p role="status">{t`Loading web telemetry settings…`}</p>;
  if (query.error || !draft) return <p role="alert">{t`Web telemetry settings could not load.`}</p>;
  const page = (patch: Partial<WebTelemetryConfig["pageview"]>) => setDraft({ ...draft, pageview: { ...draft.pageview, ...patch } });
  const replay = (patch: Partial<WebTelemetryConfig["replay"]>) => setDraft({ ...draft, replay: { ...draft.replay, ...patch } });
  return <section className="grid gap-3 rounded-xl border border-line p-4" aria-labelledby="telemetry-title">
    <h2 id="telemetry-title" className="title-section">{t`Web telemetry`}</h2>
    <p>{t`Collection starts only after a visitor consents. Project identifiers are public.`}</p>
    <label>{t`Page analytics`}<select value={draft.pageview.provider} onChange={e => page({ provider: e.target.value as WebTelemetryConfig["pageview"]["provider"], ...(e.target.value === "firebase" ? { site_id: "" } : {}) })}>
      {["none", "plausible", "umami", "ga4", "firebase", "posthog"].map(x => <option key={x} value={x}>{x}</option>)}
    </select></label>
    <TelemetryProviderHelp provider={draft.pageview.provider} />
    {draft.pageview.provider !== "firebase" ? <label>{t`Site or measurement ID`}<input value={draft.pageview.site_id} onChange={e => page({ site_id: e.target.value })} /></label> : <p>{t`Enter the Firebase Analytics G- measurement ID in Firebase web configuration below.`}</p>}
    <label>{t`Approved endpoint`}<input type="url" value={draft.pageview.endpoint} onChange={e => page({ endpoint: e.target.value })} /></label>
    <label>{t`Session replay`}<select value={draft.replay.provider} onChange={e => replay({ provider: e.target.value as WebTelemetryConfig["replay"]["provider"] })}>
      {["none", "clarity", "posthog"].map(x => <option key={x} value={x}>{x}</option>)}
    </select></label>
    <TelemetryProviderHelp provider={draft.replay.provider} />
    <p>{t`PostHog replay covers anonymous public home, inventory, events, shop and booking browse pages and About. Clarity replay is limited to anonymous About visits. Private pages and detail pages stay excluded.`}</p>
    <label>{t`Replay project ID`}<input value={draft.replay.site_id} onChange={e => replay({ site_id: e.target.value })} /></label>
    <label>{t`Replay endpoint`}<input type="url" value={draft.replay.endpoint} onChange={e => replay({ endpoint: e.target.value })} /></label>
    <TelemetryDetails value={draft} onChange={setDraft} />
    <button type="button" disabled={save.isPending} onClick={() => save.mutate(draft)}>{t`Save web telemetry`}</button>
    {save.error ? <p role="alert">{save.error instanceof StructuredApiError ? save.error.message : t`Could not save web telemetry settings.`}</p> : null}
    {save.isSuccess ? <p role="status">{t`Web telemetry settings saved.`}</p> : null}
  </section>;
}



