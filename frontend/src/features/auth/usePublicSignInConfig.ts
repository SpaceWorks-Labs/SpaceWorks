import { useEffect, useState } from "react";
import type { PublicConfig } from "../../generated/api";
import { publicV1Request } from "../../lib/api";

type Switch = { enabled?: boolean };
export type PublicSignInConfig = {
  selfServeAccounts: boolean;
  passwordLogin: boolean;
  passkeysEnabled: boolean;
  /** Present only once the deployment has Turnstile keys. */
  turnstileSiteKey?: string;
};

const OPEN: PublicSignInConfig = { selfServeAccounts: true, passwordLogin: true, passkeysEnabled: false };

/**
 * The sign-in switches from `/api/v1/config`. The account switches appear only when turned off,
 * so an absent key -- and a failed request -- mean available. Passkeys are offered only when the
 * config says so (S-A's platform switch); a failed request shows no passkey control.
 */
export function usePublicSignInConfig() {
  const [config, setConfig] = useState<PublicSignInConfig>(OPEN);
  useEffect(() => {
    let active = true;
    publicV1Request<Partial<PublicConfig>>("/config").then(result => {
      if (!active) return;
      const off = (value: unknown) => (value as Switch | undefined)?.enabled === false;
      setConfig({
        selfServeAccounts: !off(result.member_accounts) && !off(result.self_registration),
        passwordLogin: !off(result.password_login),
        passkeysEnabled: result.passkeys_enabled === true,
        turnstileSiteKey: result.turnstile_site_key || undefined,
      });
    }).catch(() => { if (active) setConfig(OPEN); });
    return () => { active = false; };
  }, []);
  return config;
}
