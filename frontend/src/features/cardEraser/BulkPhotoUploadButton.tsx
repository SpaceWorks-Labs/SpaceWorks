import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { BatchKind } from "./api";
import { PhotoBatchDialog } from "./PhotoBatchDialog";

/** "Upload many photos": opens the bulk upload that matches photo file names to card holders. */
export function BulkPhotoUploadButton({ makerspaceId, kind, eventId = null, onDone }: {
  makerspaceId: number; kind: BatchKind; eventId?: number | null; onDone?: (applied: number) => void;
}) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className="desk-button min-h-11" onClick={() => setOpen(true)}>{t`Upload many photos`}</button>
    <PhotoBatchDialog open={open} makerspaceId={makerspaceId} kind={kind} eventId={eventId} onClose={() => setOpen(false)} onDone={onDone} />
  </>;
}
