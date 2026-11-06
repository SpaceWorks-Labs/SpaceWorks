import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from 'react';
import { Download, ExternalLink, Users } from 'lucide-react';
import { ErrorBlock, StatusPill } from '../../../components/ui';
import type { GalleryAsset, GalleryEntry } from './types';

export function GalleryCard({ entry, onDownload, href, renderMemberCard, action }: { entry: GalleryEntry; onDownload: (asset: GalleryAsset) => Promise<void>; href?: string;
  renderMemberCard?: (member: GalleryEntry['members'][number]) => ReactNode;
  /** #181: the People's choice vote control, when voting is open to this member. */
  action?: ReactNode;
}) {
  const [pending, setPending] = useState(false); const [error, setError] = useState<unknown>(null);
  return <article className="grid min-w-0 gap-4 rounded-xl border border-line bg-panel p-5" aria-label={entry.title}>
    <div className="flex flex-wrap items-start justify-between gap-3"><h2 className="title-section break-words">{href ? <a className="underline underline-offset-4" href={href}>{entry.title}</a> : entry.title}</h2>
      <StatusPill label={entry.files_state === 'expired' ? t`Files expired` : entry.files_state === 'withdrawn' ? t`Files private` : t`Project files available`} tone={entry.files_state === 'available' ? 'success' : 'neutral'} /></div>
    {entry.peoples_choice ? <p><StatusPill label={t`People’s choice winner`} tone="success" /></p> : null}
    {action ? <div className="flex flex-wrap items-center gap-3">{action}</div> : null}
    {entry.awards?.length ? <ul className="flex flex-wrap gap-2" aria-label={t`Awards`}>{entry.awards.map((award, index) =>
      <li key={index}><StatusPill label={t`${String(award.prize)} · rank ${String(award.rank)}`} tone="success" /></li>)}</ul> : null}
    <p className="whitespace-pre-wrap break-words text-sm text-ink">{entry.description}</p>
    {entry.members.length ? <div className="flex flex-wrap items-center gap-3 text-sm"><Users size={18} aria-hidden="true" /><span className="sr-only">{t`Public maker profiles`}</span>
      {entry.members.map(member => renderMemberCard ? <div key={member.profile_url}>{renderMemberCard(member)}</div>
        : <a key={member.profile_url} href={member.profile_url} className="inline-flex min-h-11 items-center underline underline-offset-4">{member.display_name}</a>)}</div> : null}
    {entry.files_state === 'available' ? <>
      {entry.assets.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="py-2 text-left font-semibold">{t`Project files`}</caption>
        <thead><tr><th scope="col" className="p-2">{t`Type`}</th><th scope="col" className="p-2">{t`Size`}</th><th scope="col" className="p-2">{t`Download`}</th></tr></thead>
        <tbody>{entry.assets.map(asset => <tr key={asset.public_id} className="border-t border-line"><th scope="row" className="p-2 font-medium">{asset.kind} · {asset.mime}</th>
          <td className="p-2">{new Intl.NumberFormat(formatLocale()).format(asset.bytes)} bytes</td><td className="p-2"><button type="button" className="desk-button min-h-11" disabled={pending} onClick={async () => {
            setPending(true); setError(null); try { await onDownload(asset); } catch (error) { setError(error); } finally { setPending(false); }
          }}><Download size={18} aria-hidden="true" /> {t` Download ${asset.kind}`}</button></td></tr>)}</tbody>
      </table></div> : null}
      <ul className="flex flex-wrap gap-3">{entry.links.map(link => <li key={link.url}><a className="inline-flex min-h-11 items-center gap-2 underline underline-offset-4" href={link.url} target="_blank" rel="noopener noreferrer external">
        {link.kind}<ExternalLink size={16} aria-hidden="true" /><span className="sr-only"> {t` (opens in a new tab)`}</span></a></li>)}</ul>
    </> : <p className="text-sm text-muted">{entry.files_state === 'expired' ? t`The file-retention period ended. The project record and its content hash remain.` : t`The team has made the project files private.`}</p>}
    <ErrorBlock error={error} /><p role="status" className="sr-only">{pending ? t`Preparing download…` : ''}</p>
  </article>;
}
