import { t } from "@lingui/core/macro";

import { StructuredApiError } from "../../../lib/api";

/** 403 `certification_required` on linking or replacing a machine booking: the booker or,
 * since decision 221b, the event organizer lacks the machine type's certification. */
export function certificationText(error: unknown): string | null {
  if (!(error instanceof StructuredApiError) || error.code !== "certification_required") return null;
  const names = Array.isArray(error.body.certifications)
    ? error.body.certifications.filter((name): name is string => typeof name === "string").join(", ") : "";
  return names
    ? t`The booker or the event organizer is missing a required certification for this machine (${names}). Staff with authority over the machine type may give an override reason.`
    : t`The booker or the event organizer is missing a required certification for this machine. Staff with authority over the machine type may give an override reason.`;
}
