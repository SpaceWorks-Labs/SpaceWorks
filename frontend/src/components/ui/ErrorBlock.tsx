import { t } from "@lingui/core/macro";
import { ErrorText } from "./ErrorText";
export type ErrorBlockProps = { error: unknown; className?: string; resource?: string; onRetry?: () => void };
export function ErrorBlock({ error, className = "", resource, onRetry }: ErrorBlockProps) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : t`Something went wrong.`;
  return <div className={className}><ErrorText message={message} resource={resource} onRetry={onRetry} /></div>;
}
