import { ScreenHelp } from '../../help/HelpLink';
import { FinalistsPanel } from './FinalistsPanel';
import { PrizePayoutsPanel } from './PrizePayoutsPanel';
import { ProgrammeOptionsPanel } from './ProgrammeOptionsPanel';
import { RoundProgressPanel } from './RoundProgressPanel';
import type { Round, Scope } from './types';

/** L21b organizer tools beside the rounds: progress, finalists, emails and fees, prize payouts. */
export function ManagerExtras({ scope, rounds, features, fullManager }: { scope: Scope; rounds: Round[]; features: readonly string[]; fullManager: boolean }) {
  const on = (key: string) => features.includes(key);
  return <div className="grid gap-8">
    <ScreenHelp screen="events.judging-extras" />
    <RoundProgressPanel scope={scope} rounds={rounds} />
    {on('events.finalists') ? <FinalistsPanel scope={scope} rounds={rounds} /> : null}
    {fullManager ? <ProgrammeOptionsPanel scope={scope} entryFees={on('events.entry_fees')} paidTeams={on('events.paid_teams')} /> : null}
    {on('events.prize_payouts') ? <PrizePayoutsPanel scope={scope} /> : null}
  </div>;
}
