import { useState } from 'react';
import { Field } from '../../../components/ui';
import type { GallerySearch } from './api';
import type { GalleryFieldFilter } from './types';

/** Public gallery search, sort, the award-winners filter (L21b, X54) and one control per public choice
 *  field (S7: the organiser marks a final-stage choice field public). All of it runs on the server. */
export function GallerySearchBar({ value, onChange, unavailable, filters = [] }: {
  value: GallerySearch; onChange: (next: GallerySearch) => void; unavailable: boolean; filters?: GalleryFieldFilter[];
}) {
  const [text, setText] = useState(value.q ?? '');
  const choose = (key: string, choice: string) => {
    const fields = { ...value.fields };
    if (choice) fields[key] = choice; else delete fields[key];
    onChange({ ...value, fields });
  };
  return <form role="search" className="grid gap-3 sm:flex sm:flex-wrap sm:items-end" onSubmit={event => { event.preventDefault(); onChange({ ...value, q: text }); }}>
    <Field label="Search projects"><input className="desk-input min-h-11" type="search" maxLength={100} value={text} onChange={e => setText(e.target.value)} /></Field>
    <Field label="Sort"><select className="desk-input min-h-11" value={value.sort ?? 'newest'} onChange={e => onChange({ ...value, sort: e.target.value as GallerySearch['sort'] })}>
      <option value="newest">Newest first</option><option value="az">A to Z</option><option value="awards">Award winners first</option></select></Field>
    {filters.map(filter => <Field key={filter.key} label={filter.label}>
      <select className="desk-input min-h-11" value={value.fields?.[filter.key] ?? ''} onChange={e => choose(filter.key, e.target.value)}>
        <option value="">Any</option>{filter.choices.map(choice => <option key={choice} value={choice}>{choice}</option>)}</select></Field>)}
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.awards === 'only'}
      onChange={e => onChange({ ...value, awards: e.target.checked ? 'only' : undefined })} />Award winners only</label>
    <button type="submit" className="desk-button min-h-11">Search</button>
    {unavailable ? <p role="status" className="text-sm text-muted">Search is not available for this gallery. <button type="button" className="min-h-11 underline underline-offset-4"
      onClick={() => { setText(''); onChange({}); }}>Show every project</button></p> : null}
  </form>;
}
