import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from 'react';
import { Field } from '../../../components/ui';
import type { ProgrammeOptions } from './l21bApi';

/** Hack-money options: public prize amounts (G6), the claim window (G4) and the refundable deposit (G10). */
export function PrizeAndDepositFields({ options, deposits, pending, publicToggle, onSave }: { options: ProgrammeOptions; deposits: boolean;
  pending: boolean; publicToggle: ReactNode; onSave: (fields: Record<string, unknown>) => void }) {
  const [days, setDays] = useState(options.prize_claim_days ? String(options.prize_claim_days) : '');
  const [deposit, setDeposit] = useState(options.deposit_amount ?? '');
  const [needsSubmission, setNeedsSubmission] = useState(options.deposit_requires_submission);
  const settled = Boolean(options.deposits_settled_at);
  const claimDays = days.trim() ? Number(days.trim()) : null;
  const daysValid = claimDays === null || (Number.isInteger(claimDays) && claimDays >= 1 && claimDays <= 365);
  return <>
    <fieldset className="grid gap-3" disabled={pending}><legend className="font-semibold">{t`Prizes`}</legend>
      {publicToggle}
      <Field label={t`Days winners have to claim a prize`} hint={t`Counted from when results are announced. Leave empty for no deadline; after it, staff may mark an unclaimed prize forfeited.`}>
        <input className="desk-input min-h-11" inputMode="numeric" value={days} onChange={e => setDays(e.target.value)} aria-invalid={!daysValid} />
      </Field>
      <button type="button" className="desk-button min-h-11 justify-self-start" disabled={!daysValid}
        onClick={() => onSave({ prize_claim_days: claimDays })}>{t`Save claim window`}</button>
    </fieldset>
    {deposits ? <fieldset className="grid gap-3" disabled={pending || settled}>
      <legend className="font-semibold">{t`Refundable deposit (${options.currency.toUpperCase()})`}</legend>
      <p className="text-sm text-muted">{settled
        ? t`Deposits for this event were settled, so the deposit can no longer change.`
        : t`Charged when a place is confirmed. After the event you approve one settlement: people who came get a refund case, no-shows keep the charge.`}</p>
      <Field label={t`Deposit per confirmed place`} hint={t`Leave empty for no deposit.`}>
        <input className="desk-input min-h-11" inputMode="decimal" value={deposit} onChange={e => setDeposit(e.target.value)} /></Field>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={needsSubmission}
        onChange={e => setNeedsSubmission(e.target.checked)} />{t`Return the deposit only to people who also submitted a project`}</label>
      <button type="button" className="desk-button-primary min-h-11 justify-self-start"
        onClick={() => onSave({ deposit_amount: deposit.trim() ? deposit.trim() : null, deposit_requires_submission: needsSubmission })}>{t`Save deposit`}</button>
    </fieldset> : null}
  </>;
}
