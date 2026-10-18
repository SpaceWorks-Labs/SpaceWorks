import { useRef } from "react";
/** Keep identical retries idempotent after an ambiguous network failure. Memory only; no PII storage. */
export function useOperationId() {
  const attempt = useRef({ fingerprint: "", operation: "" });
  return (input: unknown) => {
    const fingerprint = JSON.stringify(input);
    if (attempt.current.fingerprint !== fingerprint) attempt.current = { fingerprint, operation: crypto.randomUUID() };
    return attempt.current.operation;
  };
}
