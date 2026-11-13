import { ScreenHelp } from '../../help/HelpLink';
import { DepositsPanel } from './DepositsPanel';
import { FinalistsPanel } from './FinalistsPanel';
import { PrizeClaimsPanel } from './PrizeClaimsPanel';
import { PrizeOutcomesPanel } from './PrizeOutcomesPanel';
import { PeoplesChoicePanel } from './PeoplesChoicePanel';
import { PrizePayoutsPanel } from './PrizePayoutsPanel';
import { PrizePoolPanel } from './PrizePoolPanel';
import { ProgrammeOptionsPanel } from './ProgrammeOptionsPanel';
import { RoundProgressPanel } from './RoundProgressPanel';
import { TeamChargesPanel } from './TeamChargesPanel';
import { useStaffChargesOn } from '../useStaffChargesOn';
import type { Round, Scope } from './types';

/** L21b and hack-money organizer tools beside the rounds: progress, finalists, options and fees, team charges,
 * prize payouts, claims, outcomes and the prize pool, deposits, and People's choice (#181). */
export function ManagerExtras({ scope, rounds, features, fullManager }: { scope: Scope; rounds: Round[]; features: readonly string[]; fullManager: boolean }) {
  const on = (key: string) => features.includes(key);
  // #184: entry fees, team charges and deposits are money IN, so they follow event charges;
  // prizes and payouts are money out and stay (owner decision, register #197).
  const charges = useStaffChargesOn('events');
  const fee = (key: string) => charges && on(key);
  const payouts = on('events.prize_payouts');
  return <div className="grid gap-8">
    <ScreenHelp screen="events.judging-extras" />
    <RoundProgressPanel scope={scope} rounds={rounds} />
    {on('events.finalists') ? <FinalistsPanel scope={scope} rounds={rounds} /> : null}
    {fullManager ? <ProgrammeOptionsPanel scope={scope} entryFees={fee('events.entry_fees')} paidTeams={fee('events.paid_teams')}
      deposits={fee('events.deposits')} /> : null}
    {fee('events.paid_teams') ? <TeamChargesPanel scope={scope} /> : null}
    {payouts ? <PrizePayoutsPanel scope={scope} claims={on('events.prize_claims')} /> : null}
    {payouts && on('events.prize_claims') ? <PrizeClaimsPanel scope={scope} /> : null}
    {payouts ? <PrizeOutcomesPanel scope={scope} /> : null}
    {payouts ? <PrizePoolPanel scope={scope} /> : null}
    {fee('events.deposits') ? <DepositsPanel scope={scope} /> : null}
    {fullManager && on('events.peoples_choice') ? <PeoplesChoicePanel scope={scope} payouts={on('events.prize_payouts')} /> : null}
  </div>;
}
