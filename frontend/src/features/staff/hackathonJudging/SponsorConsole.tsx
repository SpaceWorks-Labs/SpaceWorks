import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DetailLayout } from '../../../components/layouts';
import { ErrorBlock, Field, Pagination } from '../../../components/ui';
import { staffRequest } from '../../../lib/api';
import type { Page } from '../../events/hackathonGallery/types';
import { judgingKey, useJudging } from './api';
import type { Scope } from './types';
import { PrivateProgrammeBoundary } from '../../events/hackathonGallery/PrivateProgrammeBoundary';
import { useClearOnAccessLoss } from '../../events/hackathonGallery/accessLoss';

type SponsorProject = { snapshot_id: number; title: string; description: string; track_ids: number[]; asset_ids: number[];
  resumes: { asset_id: number; download_url: string }[]; links: { kind: string; url: string }[] };
function SponsorConsoleContent({ scope, sponsorId, sponsorName, renderProjectFiles, downloadResume, prizes }: {
  scope: Scope; sponsorId: number; sponsorName: string; renderProjectFiles: (snapshotId: number, ids: number[]) => ReactNode;
  downloadResume: (assetId: number) => Promise<void>; prizes?: { id: number; version: number; name: string }[];
}) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: [...judgingKey(scope), 'sponsor', sponsorId, page], retry: false,
    queryFn: () => staffRequest<Page<SponsorProject> & { prizes: { id: number; version: number; name: string }[] }>(`/admin/events/${scope.eventId}/sponsors/${sponsorId}/submissions/?page=${page}`) });
  const prizeOptions = prizes ?? query.data?.prizes ?? [];
  const { mutate } = useJudging(scope, false); const [prizeId, setPrizeId] = useState('');
  const [downloadError, setDownloadError] = useState<unknown>(null); const [pending, setPending] = useState(false);
  const denied = useClearOnAccessLoss(judgingKey(scope), [query.error, mutate.error, downloadError]);
  if (denied) return <ErrorBlock error={query.error || mutate.error || downloadError} />;
  return <DetailLayout title={`${sponsorName} projects`} state={{ status: query.isLoading ? 'loading' : query.isError ? 'error' : 'ready',
    error: query.error?.message, onRetry: () => void query.refetch() }} main={<div className="grid gap-5">
      <p className="text-sm text-muted">{t`Only projects in your assigned sponsor tracks appear here. Résumés appear only with the participant’s current recruiting consent.`}</p>
      <Field label={t`Sponsor prize for a winner proposal`}><select className="desk-input min-h-11" value={prizeId} onChange={e => setPrizeId(e.target.value)}>
        <option value="">{t`Choose your prize`}</option>{prizeOptions.map(prize => <option key={prize.id} value={prize.id}>{prize.name}</option>)}</select></Field>
      {!query.isError && query.data?.results.map(project => <article key={project.snapshot_id} className="grid gap-3 rounded-xl border border-line bg-panel p-4">
        <h2 className="title-section">{project.title}</h2><p className="whitespace-pre-wrap text-sm">{project.description}</p>
        {renderProjectFiles(project.snapshot_id, project.asset_ids)}
        {project.links.map(link => <a key={link.url} className="inline-flex min-h-11 items-center underline" href={link.url} rel="noopener noreferrer" target="_blank">{link.kind}<span className="sr-only"> {t` (opens in a new tab)`}</span></a>)}
        {project.resumes.map(resume => <button className="desk-button min-h-11" key={resume.asset_id} type="button" disabled={pending} onClick={async () => {
          setPending(true); setDownloadError(null); try { await downloadResume(resume.asset_id); } catch (error) { setDownloadError(error); } finally { setPending(false); }
        }}>{t`Download consented recruiting résumé ${resume.asset_id}`}</button>)}
        <button className="desk-button min-h-11" type="button" disabled={!prizeId || mutate.isPending} onClick={() => {
          const prize = prizeOptions.find(p => p.id === Number(prizeId)); if (prize) mutate.mutate({ suffix: `sponsors/${sponsorId}/prizes/${prize.id}/propose/`,
            version: prize.version, fields: { snapshot_id: project.snapshot_id } });
        }}>{t`Propose this project for your prize`}</button>
      </article>)}
      <Pagination page={page} count={query.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((query.data?.count ?? 0) / 24)} onChange={setPage} disabled={mutate.isPending || pending} />
      <ErrorBlock error={downloadError || mutate.error} />
    </div>} />;
}

export function SponsorConsole(props: Parameters<typeof SponsorConsoleContent>[0]) {
  return <PrivateProgrammeBoundary identity={`${props.scope.context}:${props.scope.actorId}:${props.scope.makerspaceId}:${props.scope.eventId}:${props.sponsorId}`}><SponsorConsoleContent {...props} /></PrivateProgrammeBoundary>;
}
