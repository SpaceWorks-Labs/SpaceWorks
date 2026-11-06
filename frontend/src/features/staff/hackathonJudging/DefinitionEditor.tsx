import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { ErrorBlock, Field, Pagination } from '../../../components/ui';
import { useDefinitions, useJudging } from './api';
import { newCriterion, RubricEditor } from './RubricEditor';
import type { Criterion, Prize, Round, Scope, Track } from './types';
import { changedFields, editableDefinition } from './definitionDraft';
import { panelIds, RoundSettingsFields, type RoundSettings } from './RoundSettingsFields';
import { RoundStageField } from './RoundStageField';

export function DefinitionEditor({ scope, pairwiseEnabled = false }: { scope: Scope; pairwiseEnabled?: boolean }) {
  const [kind, setKind] = useState<'tracks' | 'prizes' | 'judging-rounds'>('tracks');
  const [id, setId] = useState(0); const [version, setVersion] = useState(0);
  const [original, setOriginal] = useState<Record<string, unknown>>({});
  const [name, setName] = useState(''); const [description, setDescription] = useState('');
  const [mode, setMode] = useState('weighted_1_5'); const [normalization, setNormalization] = useState('none');
  const [criteria, setCriteria] = useState<Criterion[]>([newCriterion(1)]);
  const [track, setTrack] = useState(''); const [sponsor, setSponsor] = useState('');
  const [count, setCount] = useState(1); const [capacity, setCapacity] = useState(0);
  const [views, setViews] = useState(3); const [message, setMessage] = useState('');
  const [opensAt, setOpensAt] = useState(''); const [closesAt, setClosesAt] = useState('');
  const [minutesPerView, setMinutesPerView] = useState(4); const [judgingMinutes, setJudgingMinutes] = useState(45);
  const [sponsorProposal, setSponsorProposal] = useState(false);
  const [guidance, setGuidance] = useState(''); const [exploration, setExploration] = useState('0.10');
  const [page, setPage] = useState(1); const [amount, setAmount] = useState('');
  const [settings, setSettings] = useState<RoundSettings>({ visibility: 'assigned', fresh_eyes: false, panel: '' });
  const [stageId, setStageId] = useState(''); const [roundState, setRoundState] = useState('draft');
  const { tracks, prizes } = useDefinitions(scope, page); const { query: rounds, mutate } = useJudging(scope, true, false, page);
  const countRows = (kind === 'tracks' ? tracks.data?.count : kind === 'prizes' ? prizes.data?.count : rounds.data?.count) ?? 0;
  const rows = kind === 'tracks' ? tracks.data?.results : kind === 'prizes' ? prizes.data?.results : rounds.data?.results;
  const loadRecord = (row: Track | Prize | Round | undefined) => {
    setId(row?.id ?? 0); setVersion(row?.version ?? 0); setMessage('');
    setOriginal(row ? editableDefinition(row) : {});
    if (!row) { setName(''); setDescription(''); setStageId(''); setRoundState('draft'); return; }
    if ('name' in row) { setName(row.name); setDescription(row.description); }
    if ('capacity' in row) setCapacity(row.capacity);
    if ('award_count' in row) { setCount(row.award_count); setTrack(String(row.track_id ?? '')); setSponsor(String(row.sponsor_id ?? '')); setSponsorProposal(row.winner_selection_mode === 'sponsor_proposal'); setAmount(row.amount_per_winner ?? ''); }
    if ('mode' in row) { setName(row.key); setMode(row.mode); setViews(row.min_reviews); setNormalization(row.normalization); setCriteria(row.criteria);
      setOpensAt(row.opens_at ? new Date(row.opens_at).toISOString().slice(0, 16) : ''); setClosesAt(row.closes_at ? new Date(row.closes_at).toISOString().slice(0, 16) : ''); setMinutesPerView(row.minutes_per_view); setJudgingMinutes(row.judging_minutes);
      setGuidance(row.guidance ?? ''); setExploration((row.exploration ?? 0.1).toFixed(2));
      const extra = row as Round & { share_feedback?: boolean; judge_reminders?: boolean };
      setSettings({ visibility: row.visibility === 'all' ? 'all' : 'assigned', fresh_eyes: Boolean(row.fresh_eyes), panel: (row.panel ?? []).join(', '),
        share_feedback: Boolean(extra.share_feedback), judge_reminders: Boolean(extra.judge_reminders) });
      setStageId(String((row as Round & { submission_stage_id?: number | null }).submission_stage_id ?? '')); setRoundState(row.state ?? 'draft'); }
  };
  const load = (value: string) => loadRecord(rows?.find(row => row.id === Number(value)));
  const reload = async () => {
    if (kind === 'tracks') loadRecord((await tracks.refetch()).data?.results.find(row => row.id === id));
    else if (kind === 'prizes') loadRecord((await prizes.refetch()).data?.results.find(row => row.id === id));
    else loadRecord((await rounds.refetch()).data?.results.find(row => row.id === id));
  };
  return <form className="grid gap-4" onSubmit={event => {
    event.preventDefault();
    const fields = kind === 'judging-rounds' ? { key: name, mode, min_reviews: views, normalization: mode === 'weighted_1_5' ? normalization : 'none',
      opens_at: opensAt ? `${opensAt}:00Z` : null, closes_at: closesAt ? `${closesAt}:00Z` : null, minutes_per_view: minutesPerView, judging_minutes: judgingMinutes,
      visibility: settings.visibility, fresh_eyes: settings.fresh_eyes, panel: panelIds(settings.panel),
      share_feedback: Boolean(settings.share_feedback), judge_reminders: Boolean(settings.judge_reminders),
      submission_stage_id: stageId ? Number(stageId) : null,
      ...(mode === 'weighted_1_5' ? { criteria } : {}), ...(mode === 'pairwise' ? { guidance, exploration } : {}) } : { name, description, ...(kind === 'tracks' ? { capacity } : {
        amount_per_winner: amount.trim() ? amount.trim() : null,
        award_count: count, track_id: track ? Number(track) : null, sponsor_id: sponsor ? Number(sponsor) : null,
        winner_selection_mode: sponsorProposal ? 'sponsor_proposal' : 'manager' }) };
    const changes = id ? changedFields(original, fields) : fields;
    if (id && !Object.keys(changes).length) { setMessage(t`No changes to save.`); return; }
    mutate.mutate({ suffix: `${kind}/${id ? `${id}/` : ''}`, version, fields: changes, method: id ? 'PATCH' : 'POST' }, {
      onSuccess: result => { setId(result.id); setVersion(result.version); setOriginal(fields); setMessage(t`Definition saved.`); },
    });
  }}>
    <h3 className="title-section">{t`Tracks, prizes and judging rounds`}</h3>
    <Field label={t`Definition type`}><select className="desk-input min-h-11" value={kind} disabled={mutate.isPending}
      onChange={e => { setKind(e.target.value as typeof kind); setPage(1); setId(0); setVersion(0); setName(''); setDescription(''); }}>
      <option value="tracks">{t`Track`}</option><option value="prizes">{t`Prize`}</option><option value="judging-rounds">{t`Judging round`}</option>
    </select></Field>
    <Pagination page={page} count={countRows} pageSize={24} totalPages={Math.ceil(countRows / 24)} onChange={setPage} disabled={mutate.isPending} />
    <Field label={t`Create or edit`}><select className="desk-input min-h-11" value={id} disabled={mutate.isPending} onChange={e => load(e.target.value)}>
      <option value={0}>{t`Create new`}</option>{rows?.map(row => <option key={row.id} value={row.id}>{'name' in row ? row.name : row.key}</option>)}
    </select></Field>
    <Field label={kind === 'judging-rounds' ? t`Round key` : t`Name`}><input className="desk-input min-h-11" required maxLength={kind === 'judging-rounds' ? 64 : 160}
      value={name} onChange={e => setName(e.target.value)} /></Field>
    {kind !== 'judging-rounds' ? <Field label={t`Public description`}><textarea className="desk-input min-h-24" maxLength={4000} value={description} onChange={e => setDescription(e.target.value)} /></Field> : null}
    {kind === 'tracks' ? <Field label={t`Track capacity (0 means unlimited)`}><input className="desk-input min-h-11" type="number" min={0} max={100000} value={capacity} onChange={e => setCapacity(Number(e.target.value))} /></Field> : null}
    {kind === 'prizes' ? <>
      <Field label={t`Track`}><select className="desk-input min-h-11" value={track} onChange={e => setTrack(e.target.value)}><option value="">{t`All event tracks`}</option>
        {tracks.data?.results.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
      <Field label={t`Sponsor ID (optional)`}><input className="desk-input min-h-11" type="number" min={1} value={sponsor} onChange={e => setSponsor(e.target.value)} /></Field>
      <Field label={t`Award slots`}><input className="desk-input min-h-11" type="number" min={1} max={100} value={count} onChange={e => setCount(Number(e.target.value))} /></Field>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={sponsorProposal} onChange={e => setSponsorProposal(e.target.checked)} />{t`Allow the assigned sponsor to propose a winner`}</label>
      <Field label={t`Prize amount per winner (optional)`} hint={t`Paid by hand and recorded as a payout; never paid automatically.`}><input className="desk-input min-h-11" inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)} /></Field>
    </> : null}
    {kind === 'judging-rounds' ? <>
      <Field label={t`Scoring method`}><select className="desk-input min-h-11" value={mode} onChange={e => setMode(e.target.value)}>
        <option value="weighted_1_5">{t`Weighted 1–5 rubric`}</option><option value="top3">{t`Top-three stack ranking`}</option>
        {pairwiseEnabled || mode === 'pairwise' ? <option value="pairwise" disabled={!pairwiseEnabled}>{t`Pairwise comparison`}</option> : null}</select></Field>
      {mode === 'pairwise' ? <p className="text-sm text-muted">{t`Judges see one project at a time and say whether it beat the one before. The ranking is calculated from every valid comparison; no rubric is used.`}</p> : null}
      <Field label={t`Required nonconflicted reviews per project`}><input className="desk-input min-h-11" type="number" min={3} max={20} value={views} onChange={e => setViews(Number(e.target.value))} /></Field>
      <RoundSettingsFields value={settings} onChange={setSettings} />
      <RoundStageField eventId={scope.eventId} value={stageId} onChange={setStageId} locked={Boolean(id) && roundState !== 'draft'} />
      <Field label={t`Opens at (UTC, optional)`}><input className="desk-input min-h-11" type="datetime-local" value={opensAt} onChange={e => setOpensAt(e.target.value)} /></Field>
      <Field label={t`Closes at (UTC, optional)`}><input className="desk-input min-h-11" type="datetime-local" value={closesAt} onChange={e => setClosesAt(e.target.value)} /></Field>
      <Field label={t`Minutes per project view`}><input className="desk-input min-h-11" type="number" min={1} max={120} value={minutesPerView} onChange={e => setMinutesPerView(Number(e.target.value))} /></Field>
      <Field label={t`Judging window in minutes`}><input className="desk-input min-h-11" type="number" min={1} max={1440} value={judgingMinutes} onChange={e => setJudgingMinutes(Number(e.target.value))} /></Field>
      {mode === 'weighted_1_5' ? <><Field label={t`Final ranking normalization`}><select className="desk-input min-h-11" value={normalization} onChange={e => setNormalization(e.target.value)}>
        <option value="none">{t`Weighted average`}</option><option value="zscore">{t`Judge z-score (includes low-sample warnings)`}</option></select></Field>
        <RubricEditor value={criteria} onChange={setCriteria} disabled={mutate.isPending} /></> : null}
      {mode === 'pairwise' ? <><Field label={t`What “better” means (shown to judges)`}><textarea className="desk-input min-h-20" maxLength={500} value={guidance} onChange={e => setGuidance(e.target.value)} /></Field>
        <details><summary className="min-h-11 cursor-pointer py-3 font-semibold">{t`Advanced`}</summary>
          <Field label={t`Random picks: ${Math.round(Number(exploration) * 100)}%`} hint={t`Share of next projects picked at random among those still needing comparisons.`}>
            <input className="min-h-11 w-full" type="range" min={0} max={0.3} step={0.05} value={exploration} onChange={e => setExploration(Number(e.target.value).toFixed(2))} /></Field></details></> : null}
    </> : null}
    <ErrorBlock error={mutate.error || tracks.error || prizes.error || rounds.error} />
    {mutate.error ? <div className="grid gap-2"><p className="text-sm text-muted">{t`Your edits are still here. Review the saved version before reapplying a changed definition.`}</p>
      <button className="desk-button min-h-11" type="button" onClick={() => void reload()}>{t`Discard my edits and reload the saved definition`}</button></div> : null}
    <p role="status" className="text-sm text-muted">{message}</p>
    <button className="desk-button-primary min-h-11" disabled={mutate.isPending} type="submit">{mutate.isPending ? t`Saving…` : t`Save definition`}</button>
  </form>;
}
