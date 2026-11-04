import type { QueryClient } from "@tanstack/react-query";
import { reauthenticationKey } from "./reauthenticationApi";

/** TanStack Query keys of the account security page (S-D). */
export const passkeysKey = ["passkeys"] as const;
export const knownDevicesKey = ["knownDevices"] as const;
const meKeys = [["staff", "me"], ["member", "account", "me"]] as const;

/**
 * After a factor or device change: the lists, the auth payloads (`mfa_enrolment_due`, the grace)
 * and the two-step status (its key sits under the re-authentication prefix).
 */
export function invalidateAccountSecurity(client: QueryClient) {
  return Promise.all([passkeysKey, knownDevicesKey, reauthenticationKey, ...meKeys]
    .map(queryKey => client.invalidateQueries({ queryKey })));
}
