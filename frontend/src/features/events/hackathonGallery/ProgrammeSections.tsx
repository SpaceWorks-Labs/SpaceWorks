import { t } from "@lingui/core/macro";
import type { ReactNode } from 'react';
import { GalleryCard } from './GalleryCard';
import { galleryEntry } from './parsers';
import type { GalleryAsset } from './types';

export type ProgrammeSection = { kind: 'prizes' | 'judges' | 'mentors' | 'project_gallery' | 'results';
  layout: 'grid' | 'list'; items: Record<string, unknown>[] };
export function ProgrammeSectionContent({ section, onDownload, renderMemberCard }: {
  section: ProgrammeSection; onDownload: (asset: GalleryAsset) => Promise<void>;
  renderMemberCard: (card: { display_name: string; profile_url: string; photo_url?: string }) => ReactNode;
}) {
  const layout = section.layout === 'grid' ? 'grid gap-4 md:grid-cols-2' : 'grid gap-4';
  return <div className={layout}>{section.items.map((item, index) => {
    if (section.kind === 'project_gallery') return <GalleryCard key={String(item.public_id)} entry={galleryEntry(item)} onDownload={onDownload}
      renderMemberCard={card => renderMemberCard({ ...card, photo_url: card.photo_url ?? undefined })} />;
    if (section.kind === 'mentors' || section.kind === 'judges') {
      if (typeof item.display_name !== 'string' || typeof item.profile_url !== 'string') return null;
      return <div key={item.profile_url}>{renderMemberCard({ display_name: item.display_name, profile_url: item.profile_url,
        ...(typeof item.photo_url === 'string' ? { photo_url: item.photo_url } : {}) })}</div>;
    }
    return <article key={index} className="rounded-xl border border-line bg-panel p-4">
      <h3 className="title-section">{section.kind === 'prizes' ? String(item.name ?? '') : String(item.prize ?? '')}</h3>
      <p className="mt-2 whitespace-pre-wrap text-sm">{section.kind === 'prizes' ? String(item.description ?? '') : t`${String(item.title ?? '')} · Rank ${String(item.rank ?? '')}`}</p>
    </article>;
  })}</div>;
}

// G/pages registers this map in its renderer registry. No fallback route or global registration.
export const hackathonSectionRenderers = {
  prizes: ProgrammeSectionContent, judges: ProgrammeSectionContent, mentors: ProgrammeSectionContent,
  project_gallery: ProgrammeSectionContent, results: ProgrammeSectionContent,
};
