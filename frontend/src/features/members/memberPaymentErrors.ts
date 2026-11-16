import { t } from "@lingui/core/macro";

import { StructuredApiError } from "../../lib/api";

/**
 * Plain, actionable copy for a member's pay / "I paid" refusal. The server's refusal codes
 * (checkout, mobile intent, paid claim, pay link) name the next step the payer can take,
 * instead of a bare "Online payment is not available for this charge.".
 */
export function memberPaymentErrorText(error: unknown): string {
  if (!(error instanceof StructuredApiError)) {
    return error ? t`That did not work. Check your connection and try again.` : "";
  }
  switch (error.code) {
    case "payments_unavailable":
      return t`Online payment isn't available for this charge right now. Pay at the space, or try again later.`;
    case "payment_rail_conflict":
      return t`This charge is already being paid in the app. Finish paying there, or pay at the space.`;
    case "payment_settlement_pending":
      return t`You told the space you paid this charge. Wait for them to confirm it before paying again.`;
    case "payment_terminal":
      return t`This charge is no longer waiting for payment. Refresh to see its latest status.`;
    case "claim_exists":
      return t`You already told the space about this payment. They will confirm it soon.`;
    case "claim_date_invalid":
      return t`The payment date cannot be in the future.`;
    case "claim_reference_invalid":
      return t`Enter the 6-35 character transaction reference (UTR) from your bank or UPI app.`;
    case "feature_disabled":
      return t`The space no longer takes "I've paid" notes here. Pay at the space or contact them.`;
    case "pay_link_invalid":
      return t`This payment link has expired. Ask the space for a new link.`;
    default:
      break;
  }
  if (error.status === 404) return t`This charge is no longer waiting for payment. Refresh to see its latest status.`;
  if (error.status === 429) return t`Too many attempts. Wait a minute and try again.`;
  return error.detail ?? error.message;
}
