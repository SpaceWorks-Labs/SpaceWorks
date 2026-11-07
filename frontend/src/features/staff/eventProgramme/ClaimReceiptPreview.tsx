import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { staffRequestBlob } from "../../../lib/api";
import { payoutPath } from "../../finance/eventPayouts/api";

const PREVIEWABLE = new Set(["application/pdf", "image/png", "image/jpeg"]);

/**
 * A claim receipt opened from claim review. The bytes come from the core finance attachment
 * route, which re-checks VIEW_FINANCE and recent reauthentication; the object URL lives only
 * while this preview is open.
 */
export function ClaimReceiptPreview({ scope, assetId, onClose }: {
  scope: { actorId: number; makerspaceId: number }; assetId: number; onClose: () => void;
}) {
  const [file, setFile] = useState<{ url: string; type: string } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let url: string | null = null;
    staffRequestBlob(`${payoutPath(scope)}/attachments/${assetId}/download/`, { cache: "no-store", signal: controller.signal })
      .then(blob => { url = URL.createObjectURL(blob); setFile({ url, type: blob.type }); })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [scope.actorId, scope.makerspaceId, assetId]);
  return <section className="grid gap-3 rounded-2xl border border-line p-4" aria-label={t`Receipt ${assetId}`}>
    {failed ? <p role="alert">{t`The receipt could not be opened. Finance access, recent sign-in or the file itself may have changed.`}</p>
      : !file ? <p role="status">{t`Opening receipt…`}</p>
        : file.type === "application/pdf" ? <iframe className="h-96 w-full rounded-xl border border-line" title={t`Receipt ${assetId}`} sandbox="" src={file.url} />
          : PREVIEWABLE.has(file.type) ? <img className="max-h-96 max-w-full object-contain" src={file.url} alt={t`Receipt ${assetId}`} />
            : <p>{t`This receipt format cannot be previewed in the browser.`}</p>}
    <button type="button" className="desk-button justify-self-start" onClick={onClose}>{t`Close receipt`}</button>
  </section>;
}
