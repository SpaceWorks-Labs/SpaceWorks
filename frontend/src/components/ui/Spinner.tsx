import { t } from "@lingui/core/macro";
export function Spinner() {
  return (
    <div role="status" className="inline-flex items-center gap-3 text-muted">
      <span className="h-8 w-8 animate-spin rounded-full border-4 border-line border-t-focus" />
      <span className="sr-only">{t`Loading`}</span>
    </div>
  );
}
