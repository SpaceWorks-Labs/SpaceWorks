import { useState, type ReactNode } from 'react';
import { ListLayout, PublicDetailLayout } from '../../../components/layouts';
import { GalleryCard } from './GalleryCard';
import { usePublicGallery } from './api';
import type { GalleryAsset, GalleryEntry, Page } from './types';

export function GalleryPage({ makerspaceSlug, publicToken, eventTitle, entryPublicId, onDownload, projectHref, renderMemberCard }: {
  makerspaceSlug: string; publicToken: string; eventTitle: string; entryPublicId?: string;
  onDownload: (asset: GalleryAsset) => Promise<void>; projectHref: (id: string) => string;
  renderMemberCard: (member: GalleryEntry['members'][number]) => ReactNode;
}) {
  const [page, setPage] = useState(1); const query = usePublicGallery(makerspaceSlug, publicToken, page, entryPublicId);
  const state = { status: query.isLoading ? 'loading' as const : query.isError ? 'error' as const : 'ready' as const,
    error: query.error?.message, onRetry: () => void query.refetch() };
  if (entryPublicId) {
    const entry = query.data && 'public_id' in query.data ? query.data as GalleryEntry : null;
    return <PublicDetailLayout title={entry?.title ?? eventTitle} tagline="Made at the shared bench" state={state}
      sections={entry && !query.isError ? [{ id: 'project', label: 'The project', content: <GalleryCard entry={entry} onDownload={onDownload} renderMemberCard={renderMemberCard} /> }] : []}
      actionCard={{ title: 'Project record', state: 'done', summary: 'Published with the team’s consent.',
        doneContent: 'File access follows current consent and the event’s retention deadline.', mobileBar: { summary: eventTitle, label: 'Project record' } }} />;
  }
  const data = query.data && 'results' in query.data ? query.data as Page<GalleryEntry> : null;
  return <ListLayout header={{ title: `${eventTitle} projects`, subtitle: 'Projects shared by their teams.' }} state={state}
    empty={{ message: 'No projects are public yet.' }} isEmpty={!query.isLoading && !data?.count}
    pagination={{ page, pageSize: 24, count: data?.count ?? 0, onChange: setPage }} body={{ kind: 'rows', rows: <>
      {!query.isError && data?.results.map(entry => <GalleryCard key={entry.public_id} entry={entry} href={projectHref(entry.public_id)} onDownload={onDownload} renderMemberCard={renderMemberCard} />)}
    </> }} />;
}
