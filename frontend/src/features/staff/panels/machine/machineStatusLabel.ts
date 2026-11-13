import { t } from "@lingui/core/macro";
// Job-flow statuses whose backend word would read wrongly to staff (#141).
const LABELS: Record<string, string> = {
  changes_requested: t`Needs changes`,
  quoted: t`Quote sent`,
  uncollected: t`Not collected`,
};

/** Keep backend status words while following the product’s sentence-case voice. */
export function machineStatusLabel(status: string) {
  if (LABELS[status]) return LABELS[status];
  const words = status.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
