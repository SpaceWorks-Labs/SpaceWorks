import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../lib/api";

export function MessagingError({ error }: { error: Error | null }) {
  if (!error) return null;
  const message = error instanceof StructuredApiError && error.code === "sender_in_use"
    ? t`This sender is already in use. Choose a different sender.`
    : error instanceof StructuredApiError && ["phone_not_verified", "phone_unverified"].includes(error.code ?? "")
      ? t`Verify your phone first, then turn messaging on again.` : error.message;
  return <p role="alert" className="text-sm text-danger">{message}</p>;
}
