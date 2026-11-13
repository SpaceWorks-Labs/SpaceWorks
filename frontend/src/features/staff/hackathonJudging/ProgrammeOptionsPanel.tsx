import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { ErrorBlock, Field } from '../../../components/ui';
import { useProgrammeOptions, type ProgrammeOptions } from './l21bApi';
import { useStagePlan } from '../submissionStages/api';
import { PrizeAndDepositFields } from './ProgrammeMoneyFields';
import type { Scope } from './types';

const SWITCHES = [
  ['results_email', 'Email participants when results are announced'],
  ['submission_receipt_email', 'Email the team a receipt when a project is submitted'],
  ['finalists_email', 'Email finalists when finalists are published'],
  ['stage_reminder_email', 'Remind teams 24 hours before each submission stage deadline'],
  ['shortlist_email', 'Email teams whether they were shortlisted when a stage shortlist is published'],
] as const;

// Hack-money G2: whether a PAID entry fee opens a refund case staff decide. A pending fee is always voided.
const REFUND_SWITCHES = [
  ['refund_on_disqualification', 'Open a refund case for a paid entry fee when a project is disqualified'],
  ['refund_on_withdrawal', 'Open a refund case for a paid entry fee when a project is withdrawn'],
  ['refund_if_not_shortlisted', 'Open a refund case for a paid entry fee when a team is not shortlisted'],
] as const;

type SwitchKey = typeof SWITCHES[number][0] | typeof REFUND_SWITCHES[number][0] | 'show_prize_amounts';

/** Per-event hackathon emails (off for new events), refund rules, fees, prizes, deposits and the one-time results email. */
export function ProgrammeOptionsPanel({ scope, entryFees, paidTeams, deposits = false }: { scope: Scope; entryFees: boolean; paidTeams: boolean; deposits?: boolean }) {
  const { query, save, sendResults } = useProgrammeOptions(scope);
  const options = query.data; const resultVersion = options?.published_result_version;
  if (query.isLoading) return <LogoLoader label={t`Loading programme options…`} />;
  if (!options) return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  const toggle = (key: SwitchKey, label: string) => <label key={key} className="flex min-h-11 items-center gap-3">
    <input type="checkbox" checked={Boolean(options[key])}
      onChange={e => save.mutate({ version: options.version, fields: { [key]: e.target.checked } })} />{label}</label>;
  return <section className="grid gap-4" aria-label={t`Programme emails and fees`}>
    <h3 className="title-section">{t`Emails and fees`}</h3>
    <ErrorBlock error={save.error || sendResults.error} />
    <fieldset className="grid gap-2" disabled={save.isPending}><legend className="font-semibold">{t`Emails`}</legend>
      {SWITCHES.map(([key, label]) => toggle(key, label))}
    </fieldset>
    {entryFees || paidTeams ? <fieldset className="grid gap-2" disabled={save.isPending}><legend className="font-semibold">{t`Refund cases for entry fees`}</legend>
      <p className="text-sm text-muted">{t`A refund case is only opened; staff still approve every refund.`}</p>
      {REFUND_SWITCHES.map(([key, label]) => toggle(key, label))}
    </fieldset> : null}
    {entryFees && options.entry_fee ? <EntryFeeStage scope={scope} options={options} pending={save.isPending}
      onSave={stage => save.mutate({ version: options.version, fields: { entry_fee_stage: stage } })} /> : null}
    {entryFees || paidTeams ? <FeeEditor options={options} entryFees={entryFees} paidTeams={paidTeams} pending={save.isPending}
      onSave={fields => save.mutate({ version: options.version, fields })} /> : null}
    <PrizeAndDepositFields key={options.version} options={options} deposits={deposits} pending={save.isPending}
      publicToggle={toggle('show_prize_amounts', 'Show prizes and amounts on the public event page')}
      onSave={fields => save.mutate({ version: options.version, fields })} />
    {resultVersion ? <div className="grid gap-2"><p className="text-sm text-muted">{options.results_email_sent
      ? t`The results email has been sent for the published results.` : t`The results email has not been sent for the published results.`}</p>
      <button type="button" className="desk-button min-h-11 justify-self-start" disabled={options.results_email_sent || sendResults.isPending}
        onClick={() => sendResults.mutate(resultVersion)}>{t`Send results email now`}</button></div> : null}
  </section>;
}

function FeeEditor({ options, entryFees, paidTeams, pending, onSave }: { options: ProgrammeOptions; entryFees: boolean; paidTeams: boolean;
  pending: boolean; onSave: (fields: Record<string, unknown>) => void }) {
  const [entry, setEntry] = useState(options.entry_fee ?? ''); const [team, setTeam] = useState(options.team_fee ?? '');
  const value = (text: string) => (text.trim() ? text.trim() : null);
  return <fieldset className="grid gap-3" disabled={pending}><legend className="font-semibold">{t`Fees (${options.currency.toUpperCase()})`}</legend>
    {entryFees ? <Field label={t`Entry fee per project`} hint={t`The project stays a draft until this is paid or waived.`}><input className="desk-input min-h-11" inputMode="decimal" value={entry} onChange={e => setEntry(e.target.value)} /></Field> : null}
    {paidTeams ? <Field label={t`Team registration price`} hint={t`One fixed price per team, paid once by the leader after the team is confirmed.`}><input className="desk-input min-h-11" inputMode="decimal" value={team} onChange={e => setTeam(e.target.value)} /></Field> : null}
    <button type="button" className="desk-button-primary min-h-11 justify-self-start"
      onClick={() => onSave({ ...(entryFees ? { entry_fee: value(entry) } : {}), ...(paidTeams ? { team_fee: value(team) } : {}) })}>{t`Save fees`}</button>
  </fieldset>;
}

/** S17: one entry fee per project, due before this stage (the first by default). */
function EntryFeeStage({ scope, options, pending, onSave }: { scope: Scope; options: ProgrammeOptions; pending: boolean; onSave: (stage: number) => void }) {
  const stages = useStagePlan(scope.eventId).data?.stages ?? [];
  if (stages.length < 2) return null;
  return <Field label={t`Entry fee is due before`} hint={t`Earlier stages are free; the fee is still one fee per project.`}>
    <select className="desk-input min-h-11" disabled={pending} value={options.entry_fee_stage ?? 1} onChange={e => onSave(Number(e.target.value))}>
      {stages.map(stage => <option key={stage.position} value={stage.position}>{t`Stage ${stage.position}: ${stage.name}`}</option>)}</select></Field>;
}
