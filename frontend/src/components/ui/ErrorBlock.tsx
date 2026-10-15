import { ErrorText } from "./ErrorText";
export type ErrorBlockProps = { error: unknown; className?: string; resource?: string; onRetry?: () => void };
export function ErrorBlock({ error, className = "", resource, onRetry }: ErrorBlockProps) {
  if (!(error instanceof Error)) return null;
  return <div className={className}><ErrorText message={error.message} resource={resource} onRetry={onRetry} /></div>;
}
