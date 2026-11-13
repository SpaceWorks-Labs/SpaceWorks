import { t } from "@lingui/core/macro";
import { BOX, ensureBoxCss } from "./boxOpen/shared";

/**
 * The loading state for a whole page or panel: the Space Works box opens, holds, folds shut and
 * repeats (the same solved-from-the-symbol animation as the cold-start splash). Small and centred,
 * with the logo for the current theme; under reduced motion it is the still, open logo. Buttons, fields and
 * table rows use the small `BoxSpinner` of the same artwork. Announces `label` (default
 * "Loading") as a polite status; `showLabel` also prints it under the logo. Never focusable.
 */
export function LogoLoader({ label, size = 72, className = "min-h-40 py-10", showLabel = false }: {
  label?: string; size?: number; className?: string; showLabel?: boolean;
}) {
  ensureBoxCss();
  return <div role="status" aria-label={label ?? t`Loading`} className={`sw-box-loader grid w-full place-items-center gap-2 ${className}`}>
    <div className="sw-box loop" aria-hidden="true" style={{ width: size * 136 / 126, height: size }} dangerouslySetInnerHTML={{ __html: BOX }} />
    <span className={showLabel ? "text-sm font-semibold text-muted" : "sr-only"}>{label ?? t`Loading`}</span>
  </div>;
}
