import { t } from "@lingui/core/macro";
export type ErrorTextProps = { message?: string | null; resource?: string; onRetry?: () => void };
export function ErrorText({ message, resource, onRetry }: ErrorTextProps) {
  if (!message && !resource) return null;
  return <div role="alert" className="flex flex-wrap items-center gap-3 rounded-control border border-danger-line bg-panel px-3 py-2 text-sm text-danger">
    <p>{resource && onRetry ? t`Couldn't load ${resource}. Try again.` : message ?? t`This content is no longer available for your access.`}</p>
    {onRetry ? <button type="button" className="desk-button ml-auto" onClick={onRetry}>{t`Retry`}</button> : null}
  </div>;
}
