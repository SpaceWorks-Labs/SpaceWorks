import { t } from "@lingui/core/macro";
import { SuccessCard } from "../../components/delight/SuccessCard";

export function LoanResult({ resultId, name, outcome }: {
  resultId: string; name: string; outcome: "issued" | "returned" | "already_processed" | "blocked";
}) {
  const kind = outcome === "already_processed" ? "already" : outcome === "blocked" ? "blocked" : "success";
  const message = outcome === "issued" ? "Hardware issue recorded." : outcome === "returned" ? "Return recorded. Ready for the next maker."
    : outcome === "already_processed" ? t`This handover was already recorded.` : t`Handover wasn't recorded. Review the request status.`;
  return <SuccessCard kind={kind} name={name} message={message} resultId={resultId} />;
}
