import { t } from "@lingui/core/macro";
import { Clock } from "lucide-react";
import { formatDateTime } from "../../lib/format";

/**
 * The pay window (parity E-B5/E-F3, `events.pay_window`): an approved or promoted paid place is held until `pay_by`,
 * then released to the next person. Guests see when to pay by; staff see the same deadline beside the guest.
 */
export function PayByNotice({ payBy, audience }: { payBy?: string | null; audience: "guest" | "staff" }) {
  if (!payBy) return null;
  const when = formatDateTime(payBy);
  const overdue = new Date(payBy).getTime() < Date.now();
  return <p className={`mt-1 flex items-start gap-1.5 text-sm ${overdue ? "text-danger" : "text-warn-ink"}`}>
    <Clock size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
    <span>{audience === "guest"
      ? overdue ? t`The time to pay for this place has passed. It may be offered to someone else.` : t`Pay by ${when} to keep your place.`
      : overdue ? t`Pay window ended ${when}` : t`Pay by ${when}`}</span>
  </p>;
}
