import { t } from "@lingui/core/macro";

import { StructuredApiError } from "../../../lib/api";

/** 403 `no_machine_access` / `machine_access_expired` on linking or replacing a machine booking: the booker or,
 * since decision 221b, the event organizer has no machine access grant for the machine (decision 319).
 * A space manager gives access in Machines > Machine access; there is no override any more. */
export function machineAccessText(error: unknown): string | null {
  if (!(error instanceof StructuredApiError)) return null;
  if (error.code === "machine_access_expired") return t`The booker or the event organizer's access to this machine has ended. A space manager can renew it in Machines, under Machine access.`;
  if (error.code === "no_machine_access") return t`The booker or the event organizer has not been given access to this machine. A space manager can give it in Machines, under Machine access.`;
  return null;
}
