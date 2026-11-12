import { t } from "@lingui/core/macro";
import { useEffect, useState } from 'react';
import { SegmentedControl } from '../../../components/ui';
import type { AssignmentPage, AssignmentState } from './api';
import { SearchField } from "../../../components/ui/SearchField";

export type JudgeFilters = { state: AssignmentState | ''; q: string };
const STATE_LABELS = (): Record<AssignmentState, string> => ({ assigned: t`To score`, scored: t`Scored`, skipped: t`Skipped`,
  recused: t`Recused`, invalidated: t`Withdrawn` });

/** D13: filter a judge's own list by state (each option shows how many match the search) and search by title. */
export function JudgeListFilters({ value, counts, onChange }: { value: JudgeFilters; counts: AssignmentPage['state_counts'];
  onChange: (value: JudgeFilters) => void }) {
  const [text, setText] = useState(value.q);
  useEffect(() => {
    if (text === value.q) return;
    const timer = setTimeout(() => onChange({ ...value, q: text }), 300);
    return () => clearTimeout(timer);
  }, [text, value, onChange]);
  const labels = STATE_LABELS();
  const total = Object.values(counts ?? {}).reduce((sum, count) => sum + (count ?? 0), 0);
  const withCount = (label: string, count?: number) => counts ? t`${label} (${count ?? 0})` : label;
  const shown = (Object.keys(labels) as AssignmentState[]).filter(key => key !== 'invalidated' || (counts?.invalidated ?? 0) > 0 || value.state === key);
  return <div className="flex flex-wrap items-end gap-3">
    <SegmentedControl label={t`Show projects`} value={value.state} onChange={state => onChange({ ...value, state: state as JudgeFilters['state'] })}
      options={[{ value: '', label: withCount(t`All`, total) }, ...shown.map(key => ({ value: key, label: withCount(labels[key], counts?.[key]) }))]} />
    <label className="grid min-w-[min(16rem,100%)] flex-1 gap-1 text-sm font-semibold text-ink">{t`Search your projects`}
      <SearchField className="desk-input min-h-11 w-full" maxLength={100} value={text} onChange={e => setText(e.target.value)}
        placeholder={t`Project title`} /></label>
  </div>;
}
