import { t } from "@lingui/core/macro";
import { Link } from "react-router-dom";
import { ExternalLink } from "./ExternalLink";
import { GITHUB_URL } from "./hubLinks";
import { useLandingEnabled } from "./useLandingEnabled";

/** Slim, wrapping hub navigation inherits the tenant palette and leaves its own bar intact. */
export function TenantHubLinks() {
  const landing = useLandingEnabled();
  return <nav aria-label={t`Space Works`} className="border-b border-line bg-panel text-ink">
    <div className="sw-layout sw-layout-wide flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm">
      <Link className="desk-button-ghost" to="/">{t`Space Works`}</Link>
      <Link className="desk-button-ghost" to="/docs">{t`Docs`}</Link>
      <ExternalLink className="desk-button-ghost" href={GITHUB_URL} label={t`GitHub: the Space Works repository (opens in a new tab)`}>{t`GitHub`}</ExternalLink>
      <Link className="desk-button-ghost" to="/features">{t`Features`}</Link>
      <Link className="desk-button-ghost" to="/spaces">{t`Spaces`}</Link>
      {!landing.loading && landing.enabled ? <Link className="desk-button-ghost" to="/about">{t`About`}</Link> : null}
    </div>
  </nav>;
}
