import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";

import { capabilityOn } from "../../../lib/features";
import { guestErrorText, guestStaffApi } from "../api";
import { GuestPassScanResult, isGuestPassToken } from "./GuestPassScan";
import { LogoLoader } from "../../../components/LogoLoader";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/**
 * The staff scanner hands a guest-pass QR (`gp1.…`) to the pass check instead of the QR-label
 * resolver (decision 223 L4). Only while guest passes are on; the server also needs manage_members.
 * `intercept` returns true when it took the value.
 */
export function useGuestPassScanIntercept(space: Space) {
  const enabled = capabilityOn(space, "membership.guest_passes");
  const scan = useMutation({ mutationFn: (token: string) => guestStaffApi.scan(space.id, token.trim()) });
  const intercept = (value: string) => {
    if (!enabled || !isGuestPassToken(value)) { if (scan.data || scan.error) scan.reset(); return false; }
    scan.mutate(value);
    return true;
  };
  const panel = enabled && (scan.isPending || scan.data || scan.error) ? <div className="grid gap-2">
    {scan.isPending ? <LogoLoader label={t`Checking guest pass…`} size={48} className="min-h-16 py-3" /> : null}
    {scan.data ? <GuestPassScanResult result={scan.data} /> : null}
    {scan.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(scan.error)}</p> : null}
  </div> : null;
  return { intercept, panel };
}
