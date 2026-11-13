import { t } from "@lingui/core/macro";
import { useEffect, useState, type ReactNode } from 'react';
import { Scale } from 'lucide-react';
import { EmptyState, ErrorBlock, Field } from '../../../components/ui';
import type { PairwiseAction, PairwiseState } from './types';

type Card = NonNullable<PairwiseState['current']>;
type Send = (action: PairwiseAction, fields?: Record<string, unknown>) => void;

function editable(target: EventTarget | null) {
  return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
}

function Project({ label, card, renderAssets }: { label: string; card: Card; renderAssets: (ids: number[]) => ReactNode }) {
  return <article className="grid min-w-0 content-start gap-3 rounded-xl border border-line bg-panel p-4" aria-label={`${label}: ${card.title}`}>
    <p className="text-sm font-semibold text-muted">{label}</p>
    <h3 className="title-section break-words">{card.title}</h3>
    {card.description ? <p className="whitespace-pre-wrap break-words text-sm">{card.description}</p> : null}
    {renderAssets(card.asset_ids)}
  </article>;
}

/** One judge's pairwise desk: the project before and the one now, side by side, then a choice. */
export function PairwiseJudge({ state, onCommand, pending, error, renderAssets, onReload, shortcuts = true }: {
  state: PairwiseState; onCommand: Send; pending: boolean; error: unknown;
  renderAssets: (ids: number[]) => ReactNode; onReload: () => void;
  /** Only one desk on a page listens to the 1 / 2 / S / N keys. */
  shortcuts?: boolean;
}) {
  const [notes, setNotes] = useState(''); const [reason, setReason] = useState('');
  const allowed = (action: PairwiseAction) => !pending && state.allowed_actions.includes(action);
  useEffect(() => { setNotes(''); }, [state.current?.assignment_id]);
  const choose = (action: PairwiseAction, fields: Record<string, unknown> = {}) => { if (allowed(action)) onCommand(action, fields); };
  // Re-bound each render so the shortcut always sends the notes and actions now on screen.
  useEffect(() => {
    if (!shortcuts) return;
    const keys = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || editable(event.target)) return;
      const key = event.key.toLowerCase();
      if (key === '1' && allowed('compare')) { event.preventDefault(); onCommand('compare', { outcome: 'previous', notes }); }
      else if (key === '2' && allowed('compare')) { event.preventDefault(); onCommand('compare', { outcome: 'current', notes }); }
      else if (key === 's' && allowed('skip')) { event.preventDefault(); onCommand('skip', { notes }); }
      else if (key === 'n' && allowed('next')) { event.preventDefault(); onCommand('next', {}); }
    };
    window.addEventListener('keydown', keys);
    return () => window.removeEventListener('keydown', keys);
  });
  const progress = `${state.compared} compared · ${state.remaining} still to see`;
  return <section className="grid gap-4" aria-label={t`Pairwise round ${state.round_key}`}>
    <div className="flex flex-wrap items-start gap-3"><Scale className="mt-1 text-accent-ink" aria-hidden="true" />
      <div className="min-w-0 flex-1"><h2 className="title-panel">{t`Compare projects · ${state.round_key}`}</h2>
        <p className="text-sm text-muted">{state.guidance}</p></div>
      <p aria-live="polite" className="text-sm font-semibold tabular-nums">{progress}</p></div>
    {state.finished ? <EmptyState title={t`You have compared every project available to you`}
      description={t`Thank you. The organizer finalizes the round; your choices count once it closes.`} /> : <>
      <div className="grid gap-4 md:grid-cols-2">
        {state.previous ? <Project label={t`Before`} card={state.previous} renderAssets={renderAssets} />
          : <p className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">{t`Your first project is only viewed. From the next one on, you choose which was better.`}</p>}
        {state.current ? <Project label={t`Now`} card={state.current} renderAssets={renderAssets} />
          : <p className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">{t`Load your next project when you are ready.`}</p>}
      </div>
      {state.current ? <Field label={t`Private notes`} hint={t`Only you and the event's full managers can read these.`}>
        <textarea className="desk-input min-h-20" maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} /></Field> : null}
      <div className="flex flex-wrap gap-2">
        {state.allowed_actions.includes('compare') ? <>
          <button type="button" className="desk-button-primary min-h-11 gap-2" disabled={!allowed('compare')}
            onClick={() => choose('compare', { outcome: 'previous', notes })}>{t`Before was better `}<kbd className="text-xs">1</kbd></button>
          <button type="button" className="desk-button-primary min-h-11 gap-2" disabled={!allowed('compare')}
            onClick={() => choose('compare', { outcome: 'current', notes })}>{t`Now is better `}<kbd className="text-xs">2</kbd></button></> : null}
        {state.allowed_actions.includes('next') ? <button type="button" className="desk-button-primary min-h-11 gap-2" disabled={!allowed('next')}
          onClick={() => choose('next')}>{state.current ? t`Next project` : t`Show my next project`} <kbd className="text-xs">{t`N`}</kbd></button> : null}
        {state.allowed_actions.includes('skip') ? <button type="button" className="desk-button min-h-11 gap-2" disabled={!allowed('skip')}
          onClick={() => choose('skip', { notes })}>{t`Can't judge this one `}<kbd className="text-xs">{t`S`}</kbd></button> : null}
      </div>
      {state.allowed_actions.includes('recuse') ? <details className="rounded-xl border border-line p-3">
        <summary className="min-h-11 cursor-pointer py-2 font-semibold">{t`More: declare a conflict`}</summary>
        <div className="mt-3 grid gap-3"><Field label={t`Private reason`}><textarea className="desk-input min-h-20" maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></Field>
          <button type="button" className="desk-button min-h-11 w-fit" disabled={!allowed('recuse') || !reason.trim()}
            onClick={() => { choose('recuse', { reason }); setReason(''); }}>{t`Declare conflict and recuse`}</button></div>
      </details> : null}
    </>}
    <ErrorBlock error={error} />
    {error ? <button type="button" className="desk-button min-h-11 w-fit" disabled={pending} onClick={onReload}>{t`Reload my place in this round`}</button> : null}
  </section>;
}
