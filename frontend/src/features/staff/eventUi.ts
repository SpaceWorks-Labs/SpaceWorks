import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../lib/api";

export function eventErrorText(error: unknown) {
  if (!(error instanceof Error)) return t`Something went wrong.`;
  if (error instanceof StructuredApiError && error.code) {
    return `${error.message} (${error.code})`;
  }
  return error.message;
}
