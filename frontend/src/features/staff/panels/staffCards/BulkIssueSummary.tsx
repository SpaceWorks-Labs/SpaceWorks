import { t } from "@lingui/core/macro";

import { Callout } from "../../../../components/ui";
import type { BulkIssueResult, SkipReason, StaffCardHolder } from "./types";

const REASON_LABELS = (): Record<SkipReason, string> => ({
  not_found: t`not found in this space`, quota: t`over the monthly staff-card limit`,
  already_issued: t`already has a card`, not_eligible: t`account is disabled or restricted`,
});

/** After a bulk issue: how many were made and, for everyone skipped, the reason in plain words. */
export function BulkIssueSummary({ result, names, onDismiss }: { result: BulkIssueResult; names: StaffCardHolder[]; onDismiss: () => void }) {
  const labels = REASON_LABELS();
  const nameOf = (id: number) => names.find((holder) => holder.membership_id === id)?.name ?? t`Staff member ${id}`;
  const counts = result.skipped.reduce<Partial<Record<SkipReason, number>>>((all, item) => ({ ...all, [item.reason]: (all[item.reason] ?? 0) + 1 }), {});
  const issued = result.issued.length;
  const skipped = result.skipped.length;
  return <div role="status" className="grid gap-2 rounded-control border border-line bg-panel p-3 text-sm">
    <Callout size="inline" tone={skipped ? "warn" : "success"} lead={skipped ? t`${issued} cards issued, ${skipped} skipped.` : t`${issued} cards issued.`} />
    {skipped ? <>
      <p className="text-muted">{(Object.keys(counts) as SkipReason[]).map((reason) => `${counts[reason]} ${labels[reason]}`).join(" · ")}</p>
      <ul className="grid gap-1 text-xs text-muted">{result.skipped.map((item) => <li key={item.membership_id}>{nameOf(item.membership_id)}: {labels[item.reason]}</li>)}</ul>
    </> : null}
    <button type="button" className="desk-button-ghost min-h-11 w-fit" onClick={onDismiss}>{t`Dismiss`}</button>
  </div>;
}
