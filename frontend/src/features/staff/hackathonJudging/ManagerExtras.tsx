import { DepositsPanel } from './DepositsPanel';
import { FinalistsPanel } from './FinalistsPanel';
import { PrizeClaimsPanel } from './PrizeClaimsPanel';
import { PrizeOutcomesPanel } from './PrizeOutcomesPanel';
import { PrizePayoutsPanel } from './PrizePayoutsPanel';
import { PrizePoolPanel } from './PrizePoolPanel';
import { ProgrammeOptionsPanel } from './ProgrammeOptionsPanel';
import { RoundProgressPanel } from './RoundProgressPanel';
import { TeamChargesPanel } from './TeamChargesPanel';
import type { Round, Scope } from './types';

/** L21b and hack-money organizer tools beside the rounds: progress, finalists, options and fees, team charges,
 * prize payouts, claims, outcomes and the prize pool, and deposits. */
export function ManagerExtras({ scope, rounds, features, fullManager }: { scope: Scope; rounds: Round[]; features: readonly string[]; fullManager: boolean }) {
  const on = (key: string) => features.includes(key);
  const payouts = on('events.prize_payouts');
  return <div className="grid gap-8">
    <RoundProgressPanel scope={scope} rounds={rounds} />
    {on('events.finalists') ? <FinalistsPanel scope={scope} rounds={rounds} /> : null}
    {fullManager ? <ProgrammeOptionsPanel scope={scope} entryFees={on('events.entry_fees')} paidTeams={on('events.paid_teams')}
      deposits={on('events.deposits')} /> : null}
    {on('events.paid_teams') ? <TeamChargesPanel scope={scope} /> : null}
    {payouts ? <PrizePayoutsPanel scope={scope} claims={on('events.prize_claims')} /> : null}
    {payouts && on('events.prize_claims') ? <PrizeClaimsPanel scope={scope} /> : null}
    {payouts ? <PrizeOutcomesPanel scope={scope} /> : null}
    {payouts ? <PrizePoolPanel scope={scope} /> : null}
    {on('events.deposits') ? <DepositsPanel scope={scope} /> : null}
  </div>;
}
