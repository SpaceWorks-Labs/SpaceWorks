import { t } from "@lingui/core/macro";

import { Callout } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import type { AnalyticsProvider, AnalyticsScope } from "./analyticsApi";
import { useGrafanaMutations } from "./grafanaApi";

/** Decision 263: show Metabase, Grafana or both. Saved straight away; nothing else changes. */
export function AnalyticsProviderChoice({ scope, value }: { scope: AnalyticsScope; value: AnalyticsProvider }) {
  const { update } = useGrafanaMutations(scope);
  const options: { key: AnalyticsProvider; label: string; help: string }[] = [
    { key: "metabase", label: t`Metabase`, help: t`Dashboards from your Metabase, signed by SpaceWorks.` },
    { key: "grafana", label: t`Grafana`, help: t`Dashboards from your Grafana, as public dashboards or rendered images.` },
    { key: "both", label: t`Both`, help: t`Show Metabase and Grafana dashboards side by side.` },
  ];
  return (
    <fieldset className="grid gap-2" aria-label={t`Dashboard tool`}>
      <legend className="text-sm font-semibold text-ink">{t`Dashboard tool`}</legend>
      {options.map((option) => (
        <label key={option.key} className="flex items-start gap-2 text-sm text-ink">
          <input type="radio" name={`analytics-provider-${scope.kind}`} value={option.key}
            checked={value === option.key} disabled={update.isPending}
            onChange={() => update.mutate({ provider: option.key })} />
          <span><span className="font-semibold">{option.label}</span> <span className="text-muted">{option.help}</span></span>
        </label>
      ))}
      {update.error ? <Callout size="inline" tone="danger" lead="Not saved."
        body={update.error instanceof StructuredApiError ? update.error.message : t`Try again.`} /> : null}
    </fieldset>
  );
}
