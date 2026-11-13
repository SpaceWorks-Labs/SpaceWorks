import { analyticsTemplate, isBearerUrl } from "../webAnalytics";

export type Purpose = "analytics" | "replay" | "diagnostics";
export type Consent = Record<Purpose, boolean>;
export const deniedConsent = (): Consent => ({ analytics: false, replay: false, diagnostics: false });

/** A query or fragment is never sent or used to admit a provider. */
export function safePage(url: URL): string | null {
  if (url.username || url.password || url.origin !== window.location.origin || isBearerUrl(url)) return null;
  return analyticsTemplate(url);
}

export const consentStorageKey = (scope: string) => `spaceworks.telemetry.consent.v1:${scope}`;
const storageProbeKey = "spaceworks.telemetry.storage-probe.v1";

/** Persistence failure fails closed. Consent is local to this browser and purpose. */
export function readConsent(scope: string): Consent {
  try {
    // A readable old grant is unsafe if a later withdrawal cannot be persisted.
    localStorage.setItem(storageProbeKey, "1");
    localStorage.removeItem(storageProbeKey);
    const value: unknown = JSON.parse(localStorage.getItem(consentStorageKey(scope)) ?? "null");
    if (!value || typeof value !== "object") return deniedConsent();
    const row = value as Partial<Consent>;
    return { analytics: row.analytics === true, replay: row.replay === true, diagnostics: row.diagnostics === true };
  } catch { return deniedConsent(); }
}
export function saveConsent(scope: string, value: Consent): boolean {
  try { localStorage.setItem(consentStorageKey(scope), JSON.stringify(value)); return true; }
  catch { try { localStorage.removeItem(consentStorageKey(scope)); } catch { /* readConsent also denies grants while storage is not writable. */ } return false; }
}

