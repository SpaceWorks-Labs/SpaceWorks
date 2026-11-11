import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { ErrorBlock, Field } from '../../../components/ui';
import { useLeaderTeam } from './api';
import { fixedMoney } from '../../../lib/money';

/** The leader proposes how a cash prize is shared (G3). Each member then confirms their own share. */
export function PrizeSplitEditor({ makerspaceId, eventId, actorId, pending, onSubmit, onCancel }: {
  makerspaceId: number; eventId: number; actorId: number; pending: boolean;
  onSubmit: (shares: { member_id: number; amount: string }[]) => void; onCancel: () => void;
}) {
  const team = useLeaderTeam(makerspaceId, eventId, actorId, true);
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  if (team.isLoading) return <p role="status">{t`Loading your team…`}</p>;
  if (team.error) return <ErrorBlock error={team.error} onRetry={() => void team.refetch()} />;
  const members = team.data?.members ?? [];
  if (!members.length) return <p className="text-sm text-muted" role="status">{t`Your team roster is not available here.`}</p>;
  const rows = members.map(member => ({ member_id: member.member_id, amount: (amounts[member.member_id] ?? '').trim() }))
    .filter(row => row.amount && Number(row.amount) > 0);
  const total = rows.reduce((sum, row) => sum + Number(row.amount), 0);
  const invalid = !rows.length || rows.some(row => !/^\d+(\.\d{1,3})?$/.test(row.amount));
  return <form className="grid gap-3 rounded-xl border border-line p-4" aria-label={t`Prize split`}
    onSubmit={event => { event.preventDefault(); if (!invalid) onSubmit(rows); }}>
    <fieldset className="grid gap-3" disabled={pending}>
      <legend className="font-semibold">{t`Split the prize`}</legend>
      <p className="text-sm text-muted">{t`Enter each member's share. Leave a member empty to give them none. Your own share is confirmed now; the others confirm theirs.`}</p>
      {members.map(member => <Field key={member.member_id}
        label={member.profile?.display_name || (member.member_id === actorId ? t`You` : t`Member ${member.member_id}`)}>
        <input className="desk-input min-h-11" inputMode="decimal" value={amounts[member.member_id] ?? ''}
          onChange={event => setAmounts(value => ({ ...value, [member.member_id]: event.target.value }))} />
      </Field>)}
      <p className="text-sm" role="status">{t`Total ${fixedMoney(total)}`}</p>
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="desk-button-primary min-h-11" disabled={invalid}>{t`Propose split`}</button>
        <button type="button" className="desk-button min-h-11" onClick={onCancel}>{t`Cancel`}</button>
      </div>
    </fieldset>
  </form>;
}
