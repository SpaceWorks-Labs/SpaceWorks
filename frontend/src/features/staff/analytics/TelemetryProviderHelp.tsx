import { t } from "@lingui/core/macro";

/** The provider guide in the repository docs (decision 223 A213). */
export const TELEMETRY_DOCS_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/docs/web-telemetry-providers.md";

/** One plain sentence per provider: what to enter and what the operator must allow. */
export function telemetryProviderHelp(provider: string): string {
  switch (provider) {
    case "plausible": return t`Enter your site's domain. A self-hosted Plausible also needs its origin in the operator's allow-list.`;
    case "umami": return t`Enter the website UUID and its HTTPS origin. The operator must add that origin to the allow-list.`;
    case "ga4": return t`Enter the G- measurement ID. Google's script and collection origins must be in the operator's allow-list (WEB_TELEMETRY_ALLOWED_ORIGINS).`;
    case "firebase": return t`Fill the Firebase web configuration below and its G- measurement ID. Choose GA4 or Firebase, not both.`;
    case "posthog": return t`Enter the phc_ project key. A self-hosted or EU PostHog origin must be in the operator's allow-list.`;
    case "clarity": return t`Enter the Clarity project ID. Replay covers only the anonymous About page, fully masked. Clarity's origins must be in the operator's allow-list (WEB_TELEMETRY_ALLOWED_ORIGINS).`;
    default: return "";
  }
}

/** The help line for one provider choice, with a link to the full provider guide. */
export function TelemetryProviderHelp({ provider }: { provider: string }) {
  const text = telemetryProviderHelp(provider);
  if (!text) return null;
  return <p className="text-sm text-muted">{text}{" "}
    <a className="desk-link" href={TELEMETRY_DOCS_URL} target="_blank" rel="noreferrer">{t`Provider guide ↗`}</a></p>;
}
