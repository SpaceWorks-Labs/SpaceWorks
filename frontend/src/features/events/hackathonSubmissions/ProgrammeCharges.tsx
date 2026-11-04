import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { memberRequest } from '../../../lib/api';
import { ErrorBlock } from '../../../components/ui';
import type { ProgrammeChargeRead, ProgrammeChargesRead } from '../../../generated/api';
import { submissionKey, teamBase } from './api';
import type { SubmissionScope } from './types';

const PAID = ['paid_online', 'paid_offline', 'waived'];

/** The project's entry fee and the team's leader-paid charge (L21b). A draft stays a draft until both are settled. */
export function ProgrammeCharges({ scope, isLeader }: { scope: SubmissionScope; isLeader: boolean }) {
  const client = useQueryClient(); const key = [...submissionKey(scope), 'charges'];
  const query = useQuery({ queryKey: key, retry: false, gcTime: 0, queryFn: () => memberRequest<ProgrammeChargesRead>(`${teamBase(scope)}charges/`) });
  const raise = useMutation({ onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: () => memberRequest<ProgrammeChargeRead>(`${teamBase(scope)}charges/entry-fee/`, { method: 'POST' }) });
  const pay = useMutation({ mutationFn: (id: number) => memberRequest<{ checkout_url: string }>(`/member/makerspaces/${scope.makerspaceId}/payments/${id}/checkout`, { method: 'POST' }),
    onSuccess: data => window.location.assign(data.checkout_url) });
  const data = query.data;
  if (!data || (!data.entry_fee.required && !data.team_charge.required)) return query.error ? <ErrorBlock error={query.error} /> : null;
  const row = (label: string, charge: ProgrammeChargeRead, action?: ReactNode) => charge.required ? <li className="grid gap-1">
    <span className="font-semibold">{label}: {charge.amount} {charge.currency.toUpperCase()}</span>
    <span className="text-sm text-muted">{PAID.includes(charge.status) ? 'Settled.' : charge.status === 'not_raised' ? 'Not charged yet.' : 'Waiting for payment.'}</span>
    {!PAID.includes(charge.status) ? action : null}</li> : null;
  return <section className="grid gap-3 rounded-xl border border-line p-4" aria-label="Fees for this project">
    <h3 className="font-semibold">Fees</h3>
    <p className="text-sm text-muted">Your project stays a draft until these are paid or waived. You can also pay at the desk.</p>
    <ul className="grid gap-3">
      {row('Entry fee', data.entry_fee, data.entry_fee.payment_id
        ? <button type="button" className="desk-button min-h-11 justify-self-start" disabled={pay.isPending} onClick={() => pay.mutate(data.entry_fee.payment_id!)}>Pay entry fee online</button>
        : isLeader ? <button type="button" className="desk-button min-h-11 justify-self-start" disabled={raise.isPending} onClick={() => raise.mutate()}>Request the entry fee</button>
          : <span className="text-sm">Your team leader pays the entry fee.</span>)}
      {row('Team registration (paid once by the leader)', data.team_charge, data.team_charge.payment_id && isLeader
        ? <button type="button" className="desk-button min-h-11 justify-self-start" disabled={pay.isPending} onClick={() => pay.mutate(data.team_charge.payment_id!)}>Pay team registration online</button>
        : <span className="text-sm">The team is charged once it is confirmed.</span>)}
    </ul>
    <ErrorBlock error={query.error || raise.error || pay.error} />
  </section>;
}
