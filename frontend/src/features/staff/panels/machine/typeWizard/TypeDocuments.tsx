import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { LogoLoader } from "../../../../../components/LogoLoader";
import { ConfirmDialog } from "../../../../../components/ui";
import { deleteTypeDocument, typeDocsKey, typeDocumentUrl, uploadTypeDocument, useTypeDocuments, type TypeDocument } from "./typeSetupApi";

export const formatBytes = (value: number) => value < 1024 ? `${value} B` : value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / (1024 * 1024)).toFixed(1)} MB`;

/** The type's manuals and training material: list, upload (presign, storage, attach), open and delete. Counts against the space's storage. */
export function TypeDocuments({ makerspaceId, typeId }: { makerspaceId: number; typeId: number }) {
  const client = useQueryClient();
  const docs = useTypeDocuments(makerspaceId, typeId);
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [visible, setVisible] = useState(true);
  const [removing, setRemoving] = useState<TypeDocument | null>(null);
  const refresh = () => client.invalidateQueries({ queryKey: typeDocsKey(makerspaceId, typeId) });
  const upload = useMutation({ mutationFn: () => {
    if (!file) throw new Error(t`Choose a document to upload`);
    return uploadTypeDocument(makerspaceId, typeId, file, title.trim() || file.name, visible);
  }, onSuccess: async () => { setFile(null); setTitle(""); if (input.current) input.current.value = ""; await refresh(); } });
  const open = useMutation({ mutationFn: (id: number) => typeDocumentUrl(makerspaceId, typeId, id), onSuccess: ({ url }) => window.open(url, "_blank", "noopener,noreferrer") });
  const remove = useMutation({ mutationFn: (id: number) => deleteTypeDocument(makerspaceId, typeId, id), onSuccess: async () => { setRemoving(null); await refresh(); } });
  return <section className="grid gap-3" aria-label={t`Documents`}>
    <h4 className="title-section">{t`Documents`}</h4>
    {docs.isLoading ? <LogoLoader label={t`Loading documents…`} size={48} className="min-h-16 py-3" /> : null}
    {docs.isError ? <p role="alert" className="text-sm text-danger">{docs.error.message}</p> : null}
    {docs.isSuccess && !docs.data.length ? <p className="text-sm text-muted">{t`No documents yet. Upload a manual or training sheet below.`}</p> : null}
    <ul className="grid gap-2">{(docs.data ?? []).map(doc => <li key={doc.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-3 text-sm">
      <span className="min-w-0 break-words"><strong>{doc.title}</strong> <span className="text-muted">{[doc.original_filename, formatBytes(doc.size_bytes), doc.member_visible ? t`Members can open it` : t`Staff only`].join(" · ")}</span></span>
      <span className="flex flex-wrap gap-2"><button type="button" className="desk-button min-h-11" disabled={open.isPending} aria-label={t`Open ${doc.title}`} onClick={() => open.mutate(doc.id)}>{t`Open`}</button>
        <button type="button" className="desk-button-danger min-h-11" aria-label={t`Delete ${doc.title}`} onClick={() => { remove.reset(); setRemoving(doc); }}>{t`Delete`}</button></span></li>)}</ul>
    <form className="grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); upload.mutate(); }}>
      <label className="grid gap-1 text-sm">{t`File`}<input ref={input} className="desk-input" type="file" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
      <label className="grid gap-1 text-sm">{t`Title`}<input className="desk-input" value={title} maxLength={200} placeholder={file?.name ?? ""} onChange={event => setTitle(event.target.value)} /></label>
      <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={visible} onChange={event => setVisible(event.target.checked)} />{t`Members can open this before they use the machine`}</label>
      <div className="sm:col-span-2"><button type="submit" className="desk-button-primary min-h-11" disabled={upload.isPending || !file}>
        {upload.isPending ? <><BoxArt size={16} mono />{t`Uploading…`}</> : t`Upload`}</button></div>
    </form>
    {upload.error ? <p role="alert" className="text-sm text-danger">{upload.error.message}</p> : null}
    {open.error ? <p role="alert" className="text-sm text-danger">{open.error.message}</p> : null}
    {remove.error ? <p role="alert" className="text-sm text-danger">{remove.error.message}</p> : null}
    <ConfirmDialog open={removing !== null} tone="danger" title={t`Delete this document?`} confirmLabel={t`Delete`} pending={remove.isPending}
      message={t`Members can no longer open it. The space's storage is freed.`} onCancel={() => setRemoving(null)} onConfirm={() => { if (removing) remove.mutate(removing.id); }} />
  </section>;
}
