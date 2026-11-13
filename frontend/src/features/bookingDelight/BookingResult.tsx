import { t } from "@lingui/core/macro";
import { SuccessCard } from "../../components/delight/SuccessCard";

export function BookingResult({ resultId, name, outcome }: {
  resultId: string; name: string; outcome: "checked_in" | "already_checked_in" | "blocked";
}) {
  const kind = outcome === "checked_in" ? "success" : outcome === "already_checked_in" ? "already" : "blocked";
  const message = outcome === "checked_in" ? t`Booking check-in recorded.` : outcome === "already_checked_in" ? t`Already checked in.` : t`Check-in wasn't recorded. Review the booking status.`;
  return <SuccessCard kind={kind} name={name} message={message} resultId={resultId} />;
}
