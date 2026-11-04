import { PassState } from "../../components/delight/PassState";

/** G maps an authenticated loan workflow response, never a public inventory record. */
export function LoanPass({ title, issuedAt, returnedAt }: { title: string; issuedAt: string | null; returnedAt: string | null }) {
  const value = returnedAt ? { state: "completed" as const, label: "Returned", completedAt: returnedAt }
    : issuedAt ? { state: "completed" as const, label: "Issued", completedAt: issuedAt }
      : { state: "ready" as const, label: "Awaiting handover" };
  return <PassState title={title} value={value} />;
}
