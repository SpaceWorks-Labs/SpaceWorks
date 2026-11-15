import { t } from "@lingui/core/macro";
import { ErrorText } from "./ErrorText";
import { isRetryable } from "../../lib/api/errors";
export type ErrorBlockProps = { error: unknown; className?: string; resource?: string; onRetry?: () => void };
export function ErrorBlock({ error, className = "", resource, onRetry }: ErrorBlockProps) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : t`Something went wrong.`;
  // Decision 588: Retry only where a retry can succeed (5xx, 429, no response); a refusal shows its message alone.
  return <div className={className}><ErrorText message={message} resource={resource} onRetry={isRetryable(error) ? onRetry : undefined} /></div>;
}
