import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { CheckCircle2, ListChecks } from 'lucide-react';
import { ErrorBlock } from '../../../components/ui';
import { useAssignment } from './api';
import { useNextProject } from './l21bApi';
import type { Assignment, Scope } from './types';
import { LogoLoader } from '../../../components/LogoLoader';
import { BoxArt } from '../../../components/BoxSpinner';

export type JudgeAction = 'score' | 'rank' | 'recuse' | 'skip';
/** Submitting, recusing or skipping finishes a project; a private draft does not. */
export const finishesProject = (action: JudgeAction, fields: Record<string, unknown>) => action !== 'score' || fields.submit !== false;

/**
 * D12 "Score next": opens the judge's started project, else the eligible one with the fewest reviews, right here;
 * finishing it opens the next on its own until the round is done ("You're all caught up").
 */
export function ScoreNextBar({ scope, assignments, renderEditor, onOpen }: { scope: Scope; assignments: Assignment[];
  /** The assignment open here (or null), so the list below can leave it out instead of showing it twice. */
  onOpen?: (assignmentId: number | null) => void;
  /** Render the editor; call `afterSubmit` once the server accepted the judge's action. */
  renderEditor: (assignment: Assignment, afterSubmit: (action: JudgeAction, fields: Record<string, unknown>) => void) => ReactNode }) {
  const next = useNextProject(scope);
  const [current, setCurrent] = useState<{ roundId: number; id: number } | null>(null);
  const [caughtUp, setCaughtUp] = useState<number | null>(null);
  const opened = useAssignment(scope, current?.id ?? null);
  const heading = useRef<HTMLHeadingElement>(null);
  const roundIds = [...new Set(assignments.filter(row => row.mode === 'weighted_1_5').map(row => row.round_id))];
  const known = current ? [...new Set([...roundIds, current.roundId])] : roundIds;
  const advance = (roundId: number) => next.mutate({ roundId, version: 0 }, { onSuccess: result => {
    if (result.assignment_id) { setCaughtUp(null); setCurrent({ roundId, id: result.assignment_id }); }
    else { setCurrent(null); setCaughtUp(roundId); }
  } });
  const openedId = opened.data?.id;
  useEffect(() => { if (openedId) heading.current?.focus(); }, [openedId]);
  useEffect(() => { onOpen?.(current?.id ?? null); }, [current?.id, onOpen]);
  if (!known.length && caughtUp === null) return null;
  return <section className="grid gap-3 rounded-xl border border-line bg-panel p-4" aria-label={t`Score next project`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="flex items-center gap-2 text-sm text-muted"><ListChecks aria-hidden="true" className="size-4 text-accent-ink" />
        {t`Work through your projects one at a time. The next one opens when you submit.`}</p>
      <div className="flex flex-wrap gap-2">{known.map(roundId => <button key={roundId} type="button" className="desk-button-primary min-h-11"
        disabled={next.isPending || current?.roundId === roundId} onClick={() => advance(roundId)}>
        {known.length > 1 ? t`Score next in round ${roundId}` : t`Score next project`}</button>)}
        {current ? <button type="button" className="desk-button min-h-11" onClick={() => setCurrent(null)}>{t`Stop scoring`}</button> : null}</div>
    </div>
    <div role="status" className="text-sm">
      {next.isPending ? <><BoxArt size={16} mono />{t`Finding your next project…`}</> : null}
      {!next.isPending && caughtUp !== null ? <p className="flex items-center gap-2 font-semibold text-success-ink">
        <CheckCircle2 aria-hidden="true" className="size-4" />{t`You're all caught up. Nothing is left for you to score in this round.`}</p> : null}
    </div>
    <ErrorBlock error={next.error || opened.error} onRetry={opened.error ? () => void opened.refetch() : undefined} />
    {current && opened.data ? <div className="grid gap-3 border-t border-line pt-3">
      <h3 ref={heading} tabIndex={-1} className="title-section outline-none">{t`Now scoring: ${opened.data.title}`}</h3>
      {renderEditor(opened.data, (action, fields) => { if (finishesProject(action, fields)) advance(current.roundId); })}
    </div> : current && opened.isLoading ? <LogoLoader label={t`Opening the project…`} size={48} className="min-h-16 py-3" /> : null}
  </section>;
}
