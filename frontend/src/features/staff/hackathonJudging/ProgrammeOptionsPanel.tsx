import { useState } from 'react';
import { ErrorBlock, Field } from '../../../components/ui';
import { useProgrammeOptions, type ProgrammeOptions } from './l21bApi';
import { useStagePlan } from '../submissionStages/api';
import type { Scope } from './types';

const SWITCHES = [
  ['results_email', 'Email participants when results are announced'],
  ['submission_receipt_email', 'Email the team a receipt when a project is submitted'],
  ['finalists_email', 'Email finalists when finalists are published'],
  ['refund_on_disqualification', 'Open a refund case for a paid entry fee when a project is disqualified'],
  ['stage_reminder_email', 'Remind teams 24 hours before each submission stage deadline'],
  ['shortlist_email', 'Email teams whether they were shortlisted when a stage shortlist is published'],
] as const;

/** Per-event hackathon emails (off for new events), fees and the one-time results email. */
export function ProgrammeOptionsPanel({ scope, entryFees, paidTeams }: { scope: Scope; entryFees: boolean; paidTeams: boolean }) {
  const { query, save, sendResults } = useProgrammeOptions(scope);
  const options = query.data; const resultVersion = options?.published_result_version;
  if (query.isLoading) return <p role="status">Loading programme options…</p>;
  if (!options) return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  return <section className="grid gap-4" aria-label="Programme emails and fees">
    <h3 className="title-section">Emails and fees</h3>
    <ErrorBlock error={save.error || sendResults.error} />
    <fieldset className="grid gap-2" disabled={save.isPending}><legend className="font-semibold">Emails</legend>
      {SWITCHES.map(([key, label]) => <label key={key} className="flex min-h-11 items-center gap-3">
        <input type="checkbox" checked={Boolean(options[key])}
          onChange={e => save.mutate({ version: options.version, fields: { [key]: e.target.checked } })} />{label}</label>)}
    </fieldset>
    {entryFees && options.entry_fee ? <EntryFeeStage scope={scope} options={options} pending={save.isPending}
      onSave={stage => save.mutate({ version: options.version, fields: { entry_fee_stage: stage } })} /> : null}
    {entryFees || paidTeams ? <FeeEditor options={options} entryFees={entryFees} paidTeams={paidTeams} pending={save.isPending}
      onSave={fields => save.mutate({ version: options.version, fields })} /> : null}
    {resultVersion ? <div className="grid gap-2"><p className="text-sm text-muted">{options.results_email_sent
      ? 'The results email has been sent for the published results.' : 'The results email has not been sent for the published results.'}</p>
      <button type="button" className="desk-button min-h-11 justify-self-start" disabled={options.results_email_sent || sendResults.isPending}
        onClick={() => sendResults.mutate(resultVersion)}>Send results email now</button></div> : null}
  </section>;
}

function FeeEditor({ options, entryFees, paidTeams, pending, onSave }: { options: ProgrammeOptions; entryFees: boolean; paidTeams: boolean;
  pending: boolean; onSave: (fields: Record<string, unknown>) => void }) {
  const [entry, setEntry] = useState(options.entry_fee ?? ''); const [team, setTeam] = useState(options.team_fee ?? '');
  const value = (text: string) => (text.trim() ? text.trim() : null);
  return <fieldset className="grid gap-3" disabled={pending}><legend className="font-semibold">Fees ({options.currency.toUpperCase()})</legend>
    {entryFees ? <Field label="Entry fee per project" hint="The project stays a draft until this is paid or waived."><input className="desk-input min-h-11" inputMode="decimal" value={entry} onChange={e => setEntry(e.target.value)} /></Field> : null}
    {paidTeams ? <Field label="Team registration price" hint="One fixed price per team, paid once by the leader after the team is confirmed."><input className="desk-input min-h-11" inputMode="decimal" value={team} onChange={e => setTeam(e.target.value)} /></Field> : null}
    <button type="button" className="desk-button-primary min-h-11 justify-self-start"
      onClick={() => onSave({ ...(entryFees ? { entry_fee: value(entry) } : {}), ...(paidTeams ? { team_fee: value(team) } : {}) })}>Save fees</button>
  </fieldset>;
}

/** S17: one entry fee per project, due before this stage (the first by default). */
function EntryFeeStage({ scope, options, pending, onSave }: { scope: Scope; options: ProgrammeOptions; pending: boolean; onSave: (stage: number) => void }) {
  const stages = useStagePlan(scope.eventId).data?.stages ?? [];
  if (stages.length < 2) return null;
  return <Field label="Entry fee is due before" hint="Earlier stages are free; the fee is still one fee per project.">
    <select className="desk-input min-h-11" disabled={pending} value={options.entry_fee_stage ?? 1} onChange={e => onSave(Number(e.target.value))}>
      {stages.map(stage => <option key={stage.position} value={stage.position}>{`Stage ${stage.position}: ${stage.name}`}</option>)}</select></Field>;
}
