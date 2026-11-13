import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";

import { memberRequest } from "../../lib/api";

export type TypeGuide = {
  machine_type_id: number; machine_type_name: string; training_notes: string; notes_at_session_start: boolean; notes_at_job_request: boolean;
  documents: { id: number; title: string; content_type: string; size_bytes: number }[];
};
/** Where the guide is shown: the type page always, session start and the job request only when the space chose so. */
export type GuideMoment = "always" | "session_start" | "job_request";

export const guideKey = (makerspaceId: number, typeId: number) => ["member", "machine-type-guide", makerspaceId, typeId] as const;
export const fetchTypeGuide = (makerspaceId: number, typeId: number) => memberRequest<TypeGuide>(`/member/makerspaces/${makerspaceId}/machine-types/${typeId}/guide`);
export const fetchGuideDocumentUrl = (docId: number) => memberRequest<{ url: string }>(`/member/machine-type-documents/${docId}/url`);

/**
 * "Before you use it": a machine type's training notes and documents. It renders nothing while there is nothing to show, while loading
 * and for a refusal (a non-member gets a 403), so it can sit on any member screen without an empty box.
 */
export function MachineTypeGuide({ makerspaceId, typeId, when = "always" }: { makerspaceId?: number; typeId?: number; when?: GuideMoment }) {
  const enabled = Boolean(makerspaceId && typeId);
  const guide = useQuery({ queryKey: guideKey(makerspaceId ?? 0, typeId ?? 0), enabled, retry: false, staleTime: 60_000, queryFn: () => fetchTypeGuide(makerspaceId!, typeId!) });
  const open = useMutation({ mutationFn: fetchGuideDocumentUrl, onSuccess: ({ url }) => window.open(url, "_blank", "noopener,noreferrer") });
  const data = guide.data;
  if (!data) return null;
  if (when === "session_start" && !data.notes_at_session_start) return null;
  if (when === "job_request" && !data.notes_at_job_request) return null;
  const notes = data.training_notes.trim();
  if (!notes && !data.documents.length) return null;
  return <section className="desk-panel grid gap-3 p-4" aria-labelledby={`guide-${data.machine_type_id}`}>
    <h3 id={`guide-${data.machine_type_id}`} className="title-section">{t`Before you use it`}</h3>
    {notes ? <p className="whitespace-pre-wrap break-words text-sm">{notes}</p> : null}
    {data.documents.length ? <ul className="grid gap-1">{data.documents.map(doc => <li key={doc.id}>
      <button type="button" className="desk-button-ghost min-h-11 max-w-full justify-start break-words text-left" disabled={open.isPending} onClick={() => open.mutate(doc.id)}>{doc.title}</button></li>)}</ul> : null}
    {open.isError ? <p role="alert" className="text-sm text-danger">{t`Couldn't open that document. Try again.`}</p> : null}
  </section>;
}
