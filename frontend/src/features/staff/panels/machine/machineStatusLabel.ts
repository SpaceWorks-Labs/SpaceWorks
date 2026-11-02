// Job-flow statuses whose backend word would read wrongly to staff (#141).
const LABELS: Record<string, string> = {
  changes_requested: "Needs changes",
  quoted: "Quote sent",
  uncollected: "Not collected",
};

/** Keep backend status words while following the product’s sentence-case voice. */
export function machineStatusLabel(status: string) {
  if (LABELS[status]) return LABELS[status];
  const words = status.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
