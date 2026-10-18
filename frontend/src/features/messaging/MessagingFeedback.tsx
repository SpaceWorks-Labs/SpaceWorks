import { useState } from "react";
import { StructuredApiError } from "../../lib/api";

export function MessagingError({ error }: { error: Error | null }) {
  if (!error) return null;
  const message = error instanceof StructuredApiError && error.code === "sender_in_use"
    ? "This sender is already in use. Choose a different sender."
    : error instanceof StructuredApiError && ["phone_not_verified", "phone_unverified"].includes(error.code ?? "")
      ? "Verify your phone first, then turn messaging on again." : error.message;
  return <p role="alert" className="text-sm text-danger">{message}</p>;
}

export function CopyMessagingValue({ label, value }: { label: string; value: string }) {
  const [feedback, setFeedback] = useState("");
  return <div className="grid min-w-0 gap-2">
    <p className="text-sm font-semibold">{label}</p>
    <p className="break-all text-sm text-muted">{value || "Unavailable until the deployment callback origin and sender are configured."}</p>
    <button type="button" className="desk-button w-fit" disabled={!value} onClick={async () => {
      try { await navigator.clipboard.writeText(value); setFeedback(`${label} copied.`); }
      catch { setFeedback("Copy failed. Select and copy the value above."); }
    }}>Copy {label}</button>
    <p role="status" className="text-sm text-muted">{feedback}</p>
  </div>;
}
