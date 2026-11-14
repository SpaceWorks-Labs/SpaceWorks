import { useCallback, useEffect, useLayoutEffect, useState, useSyncExternalStore } from "react";
import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { publicAnonymousRequest } from "../lib/api/requests";
import { useTenant } from "../lib/tenant";
import { useTenantBootstrap } from "../features/inventory/usePublicInventory";
import type { WebTelemetryConfig } from "../features/staff/analytics/telemetryApi";
import { legacySelected } from "../lib/telemetry/legacy";
import { deploymentMixpanel } from "../lib/telemetry/mixpanelConfig";
import { hasSessionIdentity } from "../lib/api/sessionTokens";
import { configuredApiUrl } from "../lib/runtimeConfig";
import { browserIdentity, markAuthPresent, resolveBrowserIdentity, subscribeBrowserIdentity } from "../lib/telemetry/sessionFence";
import { consentScope } from "../lib/telemetry/consentScope";
import { readConsent, safePage, type Consent } from "../lib/telemetry/policy";
import { telemetryScope } from "../lib/telemetry/scope";
import { stopWebTelemetry, updateWebTelemetry } from "../lib/telemetry/runtime";
import { TelemetryConsent } from "./TelemetryConsent";

const emptyConfig: WebTelemetryConfig = { pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" }, diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } }, firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" } };
type EffectiveBootstrap = { makerspace: { id: number; slug: string }; modules?: string[]; telemetry?: WebTelemetryConfig; telemetry_legacy_allowed?: boolean };
export function WebTelemetry() {
  const location = useLocation(), tenant = useTenant();
  const identityState = useSyncExternalStore(subscribeBrowserIdentity, browserIdentity);
  useEffect(() => {
    const resolve = () => { if (hasSessionIdentity("person") || hasSessionIdentity("platform")) { markAuthPresent(); return; } void resolveBrowserIdentity(`${configuredApiUrl().replace(/\/api$/, "/api/v1")}/auth/browser-state`); };
    resolve(); window.addEventListener("spaceworks-browser-state-invalidated", resolve);
    return () => window.removeEventListener("spaceworks-browser-state-invalidated", resolve);
  }, []);
  const url = new URL(`${location.pathname}${location.search}${location.hash}`, window.location.origin);
  const scope = telemetryScope(url, tenant.mode === "single", tenant.slug);
  const slug = scope.kind === "tenant" ? scope.slug : "";
  const scoped = useTenantBootstrap(slug, tenant.mode === "central" && Boolean(slug));
  const platform = useQuery({ queryKey: ["platform-telemetry-config"], queryFn: () => publicAnonymousRequest<{ platform_telemetry?: WebTelemetryConfig; platform_telemetry_legacy_allowed?: boolean }>("/config"), enabled: scope.kind === "platform" && Boolean(safePage(url)), retry: false });
  const boot = (tenant.mode === "single" ? tenant.bootstrap : scoped.data) as EffectiveBootstrap | null | undefined;
  // Positive tenant module admission; an unresolved or disabled space never inherits platform tracking.
  const mixpanel = scope.kind === "platform" || (scope.kind === "tenant" && boot?.makerspace.slug === slug && boot.modules?.includes("analytics")) ? deploymentMixpanel() : null;
  const legacyAllowed = scope.kind === "tenant" ? boot?.makerspace.slug === slug && boot.telemetry_legacy_allowed === true : scope.kind === "platform" && platform.data?.platform_telemetry_legacy_allowed === true;
  const legacy = legacySelected(scope.kind === "tenant" ? boot?.telemetry : platform.data?.platform_telemetry, legacyAllowed, Boolean(window.__WEB_ANALYTICS__));
  const config = scope.kind === "tenant" ? (boot?.makerspace.slug === slug ? boot.telemetry ?? (legacy ? emptyConfig : undefined) : undefined) : scope.kind === "platform" ? platform.data?.platform_telemetry ?? (legacy ? emptyConfig : undefined) : undefined;
  const configured = Boolean(config && (mixpanel || legacy || config.pageview.provider !== "none" || config.replay.provider !== "none"
    || config.diagnostics.sentry.enabled || config.diagnostics.firebase_performance.enabled));
  const policy = [config, legacy ? window.__WEB_ANALYTICS__ : null, ...(mixpanel ? [mixpanel] : [])];
  const identity = config ? `${scope.kind}:${boot?.makerspace.id ?? 0}:${JSON.stringify(policy)}` : "";
  const [resolved, setResolved] = useState<{ identity: string; key: string } | null>(null);
  const key = resolved?.identity === identity ? resolved.key : null;
  useLayoutEffect(() => {
    // Revoke the old generation at commit, before asynchronous consent hashing.
    // stop also preserves document isolation once provider code was admitted.
    stopWebTelemetry(); setResolved(null); if (!config || !configured) return;
    let current = true; void consentScope(scope.kind === "tenant" ? boot!.makerspace.id : 0, policy).then(value => { if (current) setResolved({ identity, key: value }); }).catch(() => undefined);
    return () => { current = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- boot and scope are covered by identity (makerspace id, scope.kind, config); re-running on a new bootstrap object would reset the resolved consent key
  }, [config, configured, identity, legacy, scope.kind, boot?.makerspace.id]);
  const onChange = useCallback((consent: Consent) => { if (key && config) void updateWebTelemetry(`${key}:${JSON.stringify(consent)}`, config, consent, new URL(window.location.href), identityState === "anonymous", legacy, mixpanel); }, [key, config, legacy, mixpanel, identityState]);
  useEffect(() => {
    if (!key || !config || !configured || !safePage(url) || identityState !== "anonymous") { stopWebTelemetry(); return; }
    onChange(readConsent(key));
  // eslint-disable-next-line react-hooks/exhaustive-deps -- url is rebuilt each render from location.pathname, search and hash, which are listed; the URL object itself is never stable
  }, [config, configured, identityState, key, onChange, location.pathname, location.search, location.hash]);
  if (!key || !config || !configured || identityState !== "anonymous" || !safePage(url)) return null;
  return <TelemetryConsent key={key} scope={key} onChange={onChange} />;
}










