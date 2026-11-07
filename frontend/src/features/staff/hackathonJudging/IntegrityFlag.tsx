import { t } from "@lingui/core/macro";
import { useQuery } from '@tanstack/react-query';
import { Info } from 'lucide-react';
import { staffRequest } from '../../../lib/api';
import { judgingKey } from './api';
import type { Scope } from './types';

type Flagged = { snapshot_id: number; submission_id: number; rule_keys: string[] };
const RULES: Record<string, string> = { github_commit_before_kickoff: 'repository has commits from before kickoff',
  github_push_after_stage_deadline: 'pushed to GitHub after the stage deadline (for information only)' };

/** Information only (#8): an info chip, never a warning colour, never an action or a verdict. */
export function IntegrityFlag({ scope, snapshotIds }: { scope: Scope; snapshotIds: number[] }) {
  const query = useQuery({ queryKey: [...judgingKey(scope), 'integrity'], retry: false,
    queryFn: () => staffRequest<{ results: Flagged[] }>(`/admin/events/${scope.eventId}/submissions/integrity/`) });
  // 404 while events.submission_integrity is off: nothing to show.
  const rows = (query.data?.results ?? []).filter(row => snapshotIds.includes(row.snapshot_id));
  if (!rows.length) return null;
  return <section aria-label={t`Integrity information`} className="grid gap-2 rounded-xl border border-line bg-info-soft p-3">
    <p className="flex items-center gap-2 text-sm font-semibold text-info-ink"><Info aria-hidden="true" className="size-4" />{t`For your information`}</p>
    <ul className="flex flex-wrap gap-2">{rows.map(row => <li key={row.snapshot_id} className="rounded-full border border-info bg-panel px-3 py-1 text-xs text-ink">
      {t`Project ${row.snapshot_id}: ${row.rule_keys.map(key => RULES[key] ?? 'information for judges').join('; ')}`}
    </li>)}</ul>
    <p className="text-xs text-muted">{t`A flag never disqualifies or hides a project. Ask the team before drawing any conclusion.`}</p>
  </section>;
}
