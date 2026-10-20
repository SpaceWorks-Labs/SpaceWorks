import { SuccessCard } from "../../components/delight/SuccessCard";

export function LoanResult({ resultId, name, outcome }: {
  resultId: string; name: string; outcome: "issued" | "returned" | "already_processed" | "blocked";
}) {
  const kind = outcome === "already_processed" ? "already" : outcome === "blocked" ? "blocked" : "success";
  const message = outcome === "issued" ? "Hardware issue recorded." : outcome === "returned" ? "Return recorded. Ready for the next maker."
    : outcome === "already_processed" ? "This handover was already recorded." : "Handover wasn't recorded. Review the request status.";
  return <SuccessCard kind={kind} name={name} message={message} resultId={resultId} celebrate={outcome === "returned"} />;
}
