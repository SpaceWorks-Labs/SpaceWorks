export type MixpanelConfig = { token: string; apiHost: string; sdkHost: string };
declare global { interface Window { __MIXPANEL__?: MixpanelConfig } }

/** Same narrow grammar as the operator settings and nginx CSP builder. */
export function deploymentMixpanel(): MixpanelConfig | null {
  const config = window.__MIXPANEL__;
  const valid = config && typeof config.token === "string" && !/\s/.test(config.token) && /^[A-Za-z0-9_-]{1,128}$/.test(config.token)
    && [config.apiHost, config.sdkHost].every(host => typeof host === "string" && !/\s/.test(host)
      && /^https:\/\/[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*(?::[0-9]{1,5})?$/.test(host));
  // URL normalization also catches case/default-port aliases of the document origin.
  try { return valid && new URL(config.sdkHost).origin !== window.location.origin ? config : null; }
  catch { return null; }
}
