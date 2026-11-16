import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../lib/api";


export function evidenceErrorText(error: unknown) {
  if (error instanceof StructuredApiError && error.status === 410) {
    const expiredAt = error.body.object_expired_at;
    const when = typeof expiredAt === "string"
      ? new Date(expiredAt).toLocaleString(formatLocale())
      : "an unknown date";
    return t`Photo expired on ${when} under retention policy.`;
  }
  return error instanceof Error ? error.message : t`Could not load evidence photo.`;
}
