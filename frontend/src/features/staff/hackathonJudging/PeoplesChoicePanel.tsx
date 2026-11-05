import { useState } from 'react';
import { Heart } from 'lucide-react';
import { EmptyState, ErrorBlock, Field, StatusPill } from '../../../components/ui';
import { useDefinitions } from './api';
import { PeoplesChoiceBallots } from './PeoplesChoiceBallots';
import { PeoplesChoicePayouts } from './PeoplesChoicePayouts';
import { usePeoplesChoice, type PeoplesChoiceSettings } from './peoplesChoiceApi';
import type { Scope } from './types';

const STATE_LABEL: Record<PeoplesChoiceSettings['state'], string> = {
  off: 'Off', scheduled: 'Voting not open yet', open: 'Voting open', closed: 'Voting closed', published: 'Published',
};
/** `datetime-local` works in the browser's zone; the API takes and returns ISO instants. */
export const toLocalInput = (value: string | null | undefined) => {
  if (!value) return '';
  const date = new Date(value); const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};
export const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null);

/** People's choice (#181): an extra award voted on the public gallery. It never changes judging. */
export function PeoplesChoicePanel({ scope, payouts }: { scope: Scope; payouts: boolean }) {
  const { settings, standings, save, publish } = usePeoplesChoice(scope);
  const row = settings.data;
  if (settings.isLoading) return <p role="status">Loading People’s choice…</p>;
  if (!row) return <ErrorBlock error={settings.error} onRetry={() => void settings.refetch()} />;
  const final = row.state === 'published';
  return <section className="grid gap-4" aria-label="People's choice">
    <div className="flex items-start gap-3"><Heart className="mt-1 text-accent" aria-hidden="true" /><div className="grid gap-1">
      <div className="flex flex-wrap items-center gap-2"><h3 className="title-section">People’s choice</h3><StatusPill label={STATE_LABEL[row.state]} tone={row.state === 'open' ? 'success' : 'neutral'} /></div>
      <p className="text-sm text-muted">Signed-in members vote once for their favourite public gallery project. It is an extra award beside judging, which it never changes. Nobody but staff sees a count until you publish.</p></div></div>
    <ErrorBlock error={save.error || publish.error} />
    {final ? <p className="text-sm text-muted" role="status">Published. The settings and ballots are final.</p>
      : <SettingsForm key={row.version} row={row} scope={scope} pending={save.isPending} onSave={fields => save.mutate({ version: row.version, fields })} />}
    {row.enabled || final ? <p className="text-sm">{row.ballots} {row.ballots === 1 ? 'ballot' : 'ballots'} counted.</p> : null}
    {standings.data ? <Standings data={standings.data} /> : <ErrorBlock error={standings.error} />}
    {row.allowed_actions.includes('publish') ? <div className="grid gap-2 rounded-xl border border-line p-4">
      <p className="text-sm">Publishing freezes this count once, names the winners (joint on a tie) and shows the award on the gallery and the event page.</p>
      <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={publish.isPending}
        onClick={() => publish.mutate(row.version)}>Publish People’s choice</button></div>
      : row.state === 'open' || row.state === 'scheduled' ? <p className="text-sm text-muted">Close voting (set the closing time to now or earlier) to publish.</p> : null}
    {row.enabled || final ? <PeoplesChoiceBallots scope={scope} /> : null}
    {final && payouts && row.prize_id ? <PeoplesChoicePayouts scope={scope} /> : null}
  </section>;
}

function SettingsForm({ row, scope, pending, onSave }: { row: PeoplesChoiceSettings; scope: Scope; pending: boolean;
  onSave: (fields: Record<string, unknown>) => void }) {
  const { prizes } = useDefinitions(scope);
  const [opens, setOpens] = useState(toLocalInput(row.opens_at)); const [closes, setCloses] = useState(toLocalInput(row.closes_at));
  const [audience, setAudience] = useState(row.audience); const [prize, setPrize] = useState(row.prize_id ?? 0);
  const [enabled, setEnabled] = useState(row.enabled); const [email, setEmail] = useState(row.open_email);
  return <fieldset className="grid gap-3 rounded-xl border border-line p-4" disabled={pending}>
    <legend className="px-1 font-semibold">Settings</legend>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Run a People’s choice vote for this event</label>
    <Field label="Who can vote"><select className="desk-input min-h-11" value={audience} onChange={e => setAudience(e.target.value as typeof audience)}>
      <option value="members">Any signed-in member</option><option value="attendees">Checked-in attendees only</option></select></Field>
    <Field label="Voting opens" hint="Leave empty to open as soon as it is switched on."><input className="desk-input min-h-11" type="datetime-local" value={opens} onChange={e => setOpens(e.target.value)} /></Field>
    <Field label="Voting closes" hint="Needed before you can publish."><input className="desk-input min-h-11" type="datetime-local" value={closes} onChange={e => setCloses(e.target.value)} /></Field>
    <Field label="Prize (optional)" hint="Use a prize you will not also award through judging."><select className="desk-input min-h-11" value={prize} onChange={e => setPrize(Number(e.target.value))}>
      <option value={0}>No prize, recognition only</option>{(prizes.data?.results ?? []).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={email} onChange={e => setEmail(e.target.checked)} />Email the event’s registrants when voting is switched on</label>
    <button type="button" className="desk-button-primary min-h-11 justify-self-start"
      onClick={() => onSave({ enabled, audience, opens_at: fromLocalInput(opens), closes_at: fromLocalInput(closes), prize_id: prize || null, open_email: email })}>Save People’s choice</button>
  </fieldset>;
}

function Standings({ data }: { data: NonNullable<ReturnType<typeof usePeoplesChoice>['standings']['data']> }) {
  if (!data.standings.length) return <EmptyState title="No votes counted yet" description="Projects appear here once members vote for them." />;
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm">
    <caption className="py-2 text-left font-semibold">{data.published ? `${data.prize_name}: published standings` : 'Live count (staff only until you publish)'}</caption>
    <thead><tr><th scope="col" className="p-2">Rank</th><th scope="col" className="p-2">Project</th><th scope="col" className="p-2">Votes</th></tr></thead>
    <tbody>{data.standings.map(row => <tr key={row.snapshot_id} className="border-t border-line"><td className="p-2">{row.rank}{row.winner ? ' · Winner' : ''}</td>
      <th scope="row" className="p-2 font-medium">{row.title}</th><td className="p-2">{row.votes}</td></tr>)}</tbody>
  </table><p className="text-sm text-muted">{data.total_votes} votes in all. Votes for a project that left the gallery are not counted.</p></div>;
}
