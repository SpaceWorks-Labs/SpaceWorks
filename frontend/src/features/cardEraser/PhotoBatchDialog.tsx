// Bulk card-photo upload, matched to holders by file name (decision 314 c addendum). Photos or a zip go up in
// small requests, the review table shows who each file matched, and nothing is attached until staff apply.
import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorText, Modal } from "../../components/ui";
import { batchApi, UPLOAD_CHUNK, UPLOAD_CHUNK_BYTES, type Batch, type BatchItem, type BatchKind } from "./api";
import { PhotoBatchReview } from "./PhotoBatchReview";
import { BoxArt } from "../../components/BoxSpinner";

const POLL_MS = 1500;
type Props = { open: boolean; makerspaceId: number; kind: BatchKind; eventId?: number | null; onClose: () => void; onDone?: (applied: number) => void };

export function PhotoBatchDialog({ open, makerspaceId, kind, eventId = null, onClose, onDone }: Props) {
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [consent, setConsent] = useState(false);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [erase, setErase] = useState(false);
  const key = ["card-photo-batch", makerspaceId, batchId] as const;
  const batch = useQuery({ queryKey: key, enabled: batchId !== null, queryFn: () => batchApi.read(makerspaceId, batchId ?? 0),
    refetchInterval: (state) => state.state.data?.state === "applying" ? POLL_MS : false });
  const data = batch.data;
  const put = (next: Batch) => client.setQueryData(key, next);

  const upload = useMutation({ mutationFn: async (files: File[]) => {
    const id = batchId ?? (await batchApi.create(makerspaceId, { kind, event_id: eventId, holders_consented: consent, remove_backgrounds: false })).id;
    setBatchId(id);
    let last: Batch | null = null;
    // Chunks of at most 20 photos and 24 MB (a lone zip is sent by itself): small, retry-friendly requests.
    for (let at = 0; at < files.length;) {
      setProgress({ done: at, total: files.length });
      let end = at, bytes = 0;
      while (end < files.length && end - at < UPLOAD_CHUNK && (end === at || bytes + files[end].size <= UPLOAD_CHUNK_BYTES)) bytes += files[end++].size;
      last = await batchApi.addFiles(makerspaceId, id, files.slice(at, end));
      at = end;
    }
    setProgress(null);
    client.setQueryData(["card-photo-batch", makerspaceId, id], last);
  }, onSettled: () => setProgress(null) });
  const choose = useMutation({ mutationFn: ({ item, body }: { item: BatchItem; body: { holder_id?: number | null; decision?: BatchItem["decision"] } }) =>
    batchApi.choose(makerspaceId, batchId ?? 0, item.id, body), onSuccess: put });
  const apply = useMutation({ mutationFn: () => batchApi.apply(makerspaceId, batchId ?? 0, data?.eraser_available ? erase : undefined), onSuccess: put });
  const cancel = useMutation({ mutationFn: () => batchApi.cancel(makerspaceId, batchId ?? 0) });

  useEffect(() => { if (data?.state === "done") onDone?.(data.applied_count); }, [data?.state, data?.applied_count, onDone]);
  const reset = () => { setBatchId(null); setConsent(false); setErase(false); setProgress(null); upload.reset(); apply.reset(); };
  const close = () => { if (data?.state === "draft") cancel.mutate(); reset(); onClose(); };
  const applying = data?.state === "applying";
  const finished = data?.state === "done";
  const waiting = data ? data.items.filter((item) => item.decision === "apply" || item.decision === "replace").length : 0;
  const error = upload.error ?? choose.error ?? apply.error;

  return <Modal open={open} onClose={close} title={t`Upload many photos`} size="xl"
    footer={<div className="flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button min-h-11" onClick={close}>{finished ? t`Close` : t`Cancel`}</button>
      {data?.state === "draft" ? <button type="button" className="desk-button-primary min-h-11" disabled={apply.isPending || waiting === 0}
        onClick={() => apply.mutate()}>{t`Apply ${waiting} photos`}</button> : null}</div>}>
    <div className="grid gap-3">
      {!data ? <>
        <p className="text-sm text-muted">{t`Choose photos or a zip. Each file is matched to a card by its name: the card number, then the email before the @, then the full name (any case, spaces, dashes or underscores). You review the matches before anything changes.`}</p>
        <label className="flex min-h-11 items-start gap-2 text-sm text-ink"><input type="checkbox" className="mt-0.5 h-5 w-5" checked={consent}
          onChange={(event) => setConsent(event.target.checked)} />
          <span>{t`The people in these photos agreed to them being stored privately and printed on their cards.`}</span></label>
        <input ref={input} type="file" multiple accept=".jpg,.jpeg,.png,.webp,.zip,image/jpeg,image/png,image/webp,application/zip"
          className="sr-only" aria-label={t`Photos or a zip of photos`}
          onChange={(event) => { const files = Array.from(event.target.files ?? []); if (files.length) upload.mutate(files); event.target.value = ""; }} />
        <div><button type="button" className="desk-button-primary min-h-11" disabled={!consent || upload.isPending} onClick={() => input.current?.click()}>
          {upload.isPending ? <><BoxArt size={16} mono />{t`Uploading…`}</> : t`Choose photos or a zip`}</button></div>
        <p className="text-xs text-muted">{t`Up to 500 photos, 8 MB each. A zip may not contain another zip.`}</p>
      </> : null}
      {progress ? <p role="status" aria-live="polite" className="text-sm text-muted">{t`Uploaded ${progress.done} of ${progress.total}…`}</p> : null}
      {data ? <>
        <p role="status" aria-live="polite" className="text-sm text-ink">{applying ? t`Applying… ${data.applied_count + data.skipped_count + data.failed_count} of ${data.file_count} done.`
          : finished ? t`Done: ${data.applied_count} photos attached, ${data.skipped_count} skipped, ${data.failed_count} failed.`
          : t`${data.file_count} photos uploaded. Check the matches, then apply.`}</p>
        {data.state === "draft" && data.eraser_available ? <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-5 w-5" checked={erase} onChange={(event) => setErase(event.target.checked)} />
          {t`Remove backgrounds after upload`}</label> : null}
        <PhotoBatchReview batch={data} disabled={data.state !== "draft" || choose.isPending}
          onChoose={(item, body) => choose.mutate({ item, body })} />
      </> : null}
      {error ? <ErrorText message={error.message} /> : null}
    </div>
  </Modal>;
}
