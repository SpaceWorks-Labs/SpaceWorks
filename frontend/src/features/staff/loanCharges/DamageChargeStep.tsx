import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Coins } from "lucide-react";

import { Modal } from "../../../components/ui";
import { capabilityOn } from "../../../lib/features";
import { staffChargesOn } from "../useStaffChargesOn";
import { formatMoney } from "../paymentsApi";
import { AccountabilityChargeForm, rowTitle } from "./AccountabilityChargeForm";
import { freeNotice, useLoanCharges } from "./LoanChargesPanel";
import { undecidedRows, type LoanAccountabilityChargeResult, type LoanAccountabilityRow } from "./loanChargesApi";

type Resolution = { damaged: number; missing: number };

/** The charge step follows a return only when loan charges (#184) and price lists are on and the return recorded damage or loss. */
export function needsDamageCharges(
  makerspace: { enabled_modules?: string[]; enabled_features?: string[] }, resolutions: Resolution[],
) {
  return staffChargesOn(makerspace, "loans") && capabilityOn(makerspace, "charges.pricing") && resolutions.some(value => value.damaged + value.missing > 0);
}

/**
 * The rows this step decides, frozen when it first loads: rows already charged before the
 * return stay in the Charges panel, and a row decided here keeps its outcome on screen.
 */
function useStepRows(makerspaceId: number, requestId: number) {
  const query = useLoanCharges(makerspaceId, requestId);
  const [ids, setIds] = useState<number[] | null>(null);
  const [outcomes, setOutcomes] = useState<Record<number, string>>({});
  const data = query.data;
  // Wait for a fetch made after mount: a cached copy from before the return has no rows yet.
  const fresh = query.isFetchedAfterMount && !query.isFetching;
  useEffect(() => {
    if (ids === null && data && fresh) setIds(undecidedRows(data).map(row => row.id));
  }, [data, ids, fresh]);
  const rows = (data?.accountability ?? []).filter(row => ids?.includes(row.id));
  const record = (row: LoanAccountabilityRow, result: LoanAccountabilityChargeResult) => setOutcomes(current => ({
    ...current, [row.id]: result.charge ? `Charged ${formatMoney(result.charge.amount, result.charge.currency)}.` : freeNotice(result.free_reason),
  }));
  return { query, ready: ids !== null, rows, outcomes, record, currency: data?.currency ?? "" };
}

function StepBody({ makerspaceId, requestId, step }: {
  makerspaceId: number; requestId: number; step: ReturnType<typeof useStepRows>;
}) {
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`The return is recorded. Set a charge for each damaged or lost item now, or decide later from the Charges section on request #${requestId}.`}</p>
    {step.rows.map(row => step.outcomes[row.id]
      ? <p key={row.id} className="rounded-xl border border-line p-3 text-sm text-ink" role="status">
        {rowTitle(row)}: {step.outcomes[row.id]}</p>
      : <AccountabilityChargeForm key={row.id} makerspaceId={makerspaceId} requestId={requestId} currency={step.currency}
        row={row} onDone={result => step.record(row, result)} />)}
  </div>;
}

/** Inline step under a return receipt. "Decide later" folds it away; nothing is lost. */
export function DamageChargeStep({ makerspaceId, requestId }: { makerspaceId: number; requestId: number }) {
  const step = useStepRows(makerspaceId, requestId);
  const [later, setLater] = useState(false);
  if (step.query.error) return null;
  if (!step.ready) return <p className="text-sm text-muted" role="status">{t`Checking damaged and lost items…`}</p>;
  if (!step.rows.length) return null;
  if (later) return <p className="text-sm text-muted">{t`Charges left for later. Set them from the Charges section on request #${requestId}.`}</p>;
  const allDone = step.rows.every(row => step.outcomes[row.id]);
  return <section aria-label={t`Charge for damaged or lost items`} className="grid gap-3 rounded-xl border border-line bg-panel p-4 text-ink">
    <h3 className="flex items-center gap-2 text-base font-semibold"><Coins aria-hidden="true" size={18} />{t`Charge for damaged or lost items`}</h3>
    <StepBody makerspaceId={makerspaceId} requestId={requestId} step={step} />
    {allDone ? null : <button className="desk-button w-full sm:w-fit" type="button" onClick={() => setLater(true)}>{t`Decide later`}</button>}
  </section>;
}

/** The same step as its own dialog, for the quick return form that closes on success. */
export function DamageChargeDialog({ makerspaceId, requestId, onClose }: {
  makerspaceId: number; requestId: number; onClose: () => void;
}) {
  const step = useStepRows(makerspaceId, requestId);
  const empty = Boolean(step.query.error) || (step.ready && !step.rows.length);
  useEffect(() => { if (empty) onClose(); }, [empty, onClose]);
  if (!step.ready || !step.rows.length) return null;
  const allDone = step.rows.every(row => step.outcomes[row.id]);
  return <Modal open onClose={onClose} title={t`Charge for damaged or lost items`}
    footer={<div className="flex justify-end">
      <button className={`${allDone ? "desk-button-primary" : "desk-button"} w-full sm:w-auto`} type="button" onClick={onClose}>
        {allDone ? t`Done` : t`Decide later`}</button>
    </div>}>
    <StepBody makerspaceId={makerspaceId} requestId={requestId} step={step} />
  </Modal>;
}
