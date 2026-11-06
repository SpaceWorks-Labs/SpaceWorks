import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { LayerDocument } from "./layout";

type LibraryRow = { id: number; name: string; version: number };
type Revision = { id: number; parameters: LayerDocument; artwork_id: number | null };
type Page<T> = { results: T[] };

export function CertificateLibrary({ makerspaceId, eventId, document, eventVersion, eventRevisionId }: { makerspaceId: number; eventId: number; document: LayerDocument; eventVersion?: number; eventRevisionId?: number | null }) {
  const [name, setName] = useState("");
  const [selected, setSelected] = useState(0);
  const base = `/admin/makerspaces/${makerspaceId}/event-certificate-library/`;
  const client = useQueryClient();
  const key = ["event-certificate-library", makerspaceId];
  const library = useQuery({ queryKey: key, queryFn: () => staffRequest<Page<LibraryRow>>(base), retry: false });
  const revisions = useQuery({ queryKey: [...key, selected], queryFn: () => staffRequest<Page<Revision>>(`${base}${selected}/revisions/`), enabled: selected > 0 });
  const save = useMutation({ mutationFn: () => staffRequest(base, { method: "POST", body: JSON.stringify({
    operation_id: crypto.randomUUID(), expected_version: 0, name, parameters: document, artwork_id: null,
  }) }), onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  const capture = useMutation({ mutationFn: (append: boolean) => staffRequest(`${base}from-event/`, { method: "POST", body: JSON.stringify({
    operation_id: crypto.randomUUID(), expected_version: append ? library.data?.results.find((row) => row.id === selected)?.version : 0,
    template_id: append ? selected : null, name, event_id: eventId, revision_id: eventRevisionId,
  }) }), onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  const copy = useMutation({ mutationFn: (revisionId: number) => staffRequest(`${base}${selected}/copy-to-event/`, {
    method: "POST", body: JSON.stringify({ event_id: eventId, revision_id: revisionId, operation_id: crypto.randomUUID(), expected_version: eventVersion }),
  }), onSuccess: () => client.invalidateQueries({ queryKey: ["events", "credentials", eventId, "certificate-design"] }) });
  const error = library.error || revisions.error || save.error || copy.error || capture.error;
  return <details className="rounded-control border border-line p-3"><summary className="min-h-11 cursor-pointer font-semibold text-ink">{t`Makerspace template library`}</summary>
    <p className="my-2 text-sm text-muted">{t`Library access needs the makerspace Event Manager role. Copies keep their own event artwork and immutable revision.`}</p>
    <div className="grid gap-3">
      <label className="grid gap-1 text-sm">{t`Template name`}<input className="desk-input" maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label>
      <button type="button" className="desk-button" disabled={!name.trim() || save.isPending} onClick={() => save.mutate()}>{t`Save draft layout to library`}</button>
      <button type="button" className="desk-button" disabled={!name.trim() || !eventRevisionId || capture.isPending} onClick={() => capture.mutate(false)}>{t`Copy saved event revision with all artwork`}</button>
      <p className="text-xs text-muted">{t`Save the event revision first to include images. The copy owns its own private artwork and stays independent of later event edits.`}</p>
      <label className="grid gap-1 text-sm">{t`Library template`}<select className="desk-input" value={selected} onChange={(event) => { const id = Number(event.target.value); setSelected(id); setName(library.data?.results.find((row) => row.id === id)?.name ?? ""); }}><option value={0}>{t`Choose a template`}</option>
        {library.data?.results.map((row) => <option value={row.id} key={row.id}>{row.name}</option>)}</select></label>
      {revisions.data?.results.map((revision) => <button key={revision.id} type="button" className="desk-button" disabled={copy.isPending || eventVersion === undefined} onClick={() => copy.mutate(revision.id)}>{t`Copy revision ${revision.id} to this event`}</button>)}
      <button type="button" className="desk-button" disabled={!selected || !eventRevisionId || !name.trim() || capture.isPending} onClick={() => capture.mutate(true)}>{t`Append saved event design and artwork as a library revision`}</button>
      {copy.isSuccess || save.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Template saved. Issued certificates keep their original design.`}</p> : null}
      {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
    </div>
  </details>;
}
