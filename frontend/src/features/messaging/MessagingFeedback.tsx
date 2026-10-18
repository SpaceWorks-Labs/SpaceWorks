import { StructuredApiError } from "../../lib/api";

export function MessagingError({ error }: { error: Error | null }) {
  if (!error) return null;
  const message = error instanceof StructuredApiError && error.code === "sender_in_use"
    ? "This sender is already in use. Choose a different sender."
    : error instanceof StructuredApiError && ["phone_not_verified", "phone_unverified"].includes(error.code ?? "")
      ? "Verify your phone first, then turn messaging on again." : error.message;
  return <p role="alert" className="text-sm text-danger">{message}</p>;
}
