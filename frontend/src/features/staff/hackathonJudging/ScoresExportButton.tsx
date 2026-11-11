import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { ErrorBlock } from '../../../components/ui';
import { staffRequestBlob } from '../../../lib/api';
import type { Round, Scope } from './types';

/** D6 (`events.scores_export`): the judging scores as CSV — raw and adjusted, per criterion, judge names; never notes. */
export function ScoresExportButton({ scope, rounds }: { scope: Scope; rounds: Round[] }) {
  const [round, setRound] = useState('');
  const scored = rounds.filter(row => row.mode !== 'pairwise' && row.state !== 'draft');
  const download = useMutation({ retry: false, mutationFn: async () => {
    const blob = await staffRequestBlob(`/admin/events/${scope.eventId}/judging/scores-export/${round ? `?round=${round}` : ''}`);
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob);
    link.download = `event-${scope.eventId}-judging-scores${round ? `-round-${round}` : ''}.csv`;
    link.click(); URL.revokeObjectURL(link.href);
  } });
  return <div className="grid gap-2">
    <div className="flex flex-wrap items-end gap-2">
      {scored.length > 1 ? <label className="grid gap-1 text-sm font-semibold text-ink">{t`Rounds in the export`}
        <select className="desk-input min-h-11" value={round} onChange={e => setRound(e.target.value)}>
          <option value="">{t`Every round`}</option>{scored.map(row => <option key={row.id} value={row.id}>{row.key}</option>)}</select></label> : null}
      <button type="button" className="desk-button inline-flex min-h-11 items-center gap-2" disabled={download.isPending} onClick={() => download.mutate()}>
        <Download aria-hidden="true" className="size-4" />{download.isPending ? t`Preparing the CSV…` : t`Download scores (CSV)`}</button>
    </div>
    <p className="text-xs text-muted">{t`Rank, reviews, raw and adjusted scores, an average per criterion and who scored. Never notes, comments or email addresses.`}</p>
    <ErrorBlock error={download.error} />
  </div>;
}
