import { t } from "@lingui/core/macro";
import { formatNumber } from "../../../lib/format";
import { useEffect, useRef, useState } from "react";
import { FileText } from "lucide-react";
import { staffRequestBlob } from "../../../lib/api";
import { payoutPath } from "./api";
import { scopeIdentity } from "./format";
import type { FinanceScope, Receipt } from "./types";
import { BoxArt } from "../../../components/BoxSpinner";

export function ReceiptViewer({ scope, receipt }: { scope: FinanceScope; receipt: Receipt }) {
  return <ReceiptContent key={`${scopeIdentity(scope.actorId, scope.makerspaceId)}:${receipt.id}:${receipt.generation}:${receipt.state}:${receipt.allowed_actions?.join()}`}
    scope={scope} receipt={receipt} />;
}

function ReceiptContent({ scope, receipt }: { scope: FinanceScope; receipt: Receipt }) {
  const [url, setUrl] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const liveUrl = useRef<string | null>(null);
  const inflight = useRef<AbortController | null>(null);
  const allowed = receipt.allowed_actions?.includes("download") === true;
  const extension = ({ "application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "image/heic": "heic", "image/heif": "heif" } as Record<string, string>)[receipt.mime] ?? "bin";
  useEffect(() => {
    const clear = () => {
      inflight.current?.abort();
      if (liveUrl.current) URL.revokeObjectURL(liveUrl.current);
      liveUrl.current = null; setUrl(null); setPending(false);
    };
    const hidden = () => { if (document.visibilityState !== "visible") clear(); };
    const timer = window.setInterval(clear, 60_000);
    window.addEventListener("blur", clear); document.addEventListener("visibilitychange", hidden);
    return () => { clear(); window.clearInterval(timer); window.removeEventListener("blur", clear); document.removeEventListener("visibilitychange", hidden); };
  }, []);
  const open = async () => {
    inflight.current?.abort();
    const controller = new AbortController(); inflight.current = controller;
    setPending(true); setError(false);
    try {
      const blob = await staffRequestBlob(`${payoutPath(scope)}/attachments/${encodeURIComponent(receipt.id)}/download/`, {
        cache: "no-store", signal: controller.signal });
      if (controller.signal.aborted || document.visibilityState !== "visible") return;
      if (!["application/pdf", "image/png", "image/jpeg", "image/heic", "image/heif"].includes(blob.type) || blob.type !== receipt.mime) throw new Error("unsupported_receipt");
      if (liveUrl.current) URL.revokeObjectURL(liveUrl.current);
      liveUrl.current = URL.createObjectURL(blob); setUrl(liveUrl.current);
    } catch { if (!controller.signal.aborted) setError(true); }
    finally { if (!controller.signal.aborted) setPending(false); }
  };
  return <article className="grid gap-3 rounded-2xl border border-line p-4">
    <h3 className="flex items-center gap-2 font-semibold"><FileText aria-hidden="true" size={18} />{t`Receipt ${receipt.id}`}</h3>
    <p className="break-all text-sm text-muted">{t`${receipt.mime} · ${formatNumber(receipt.bytes)} bytes · generation ${receipt.generation} · ${receipt.state}`}</p>
    <p className="break-all text-xs text-muted">{t`SHA-256: ${receipt.sha256}`}</p>
    {allowed ? <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => { void open(); }}>{pending ? <><BoxArt size={16} mono />{t`Opening receipt…`}</> : t`Open finance receipt`}</button>
      : <p className="text-sm text-muted">{t`Receipt bytes are unavailable. Retained metadata remains part of the financial record.`}</p>}
    {error ? <p role="alert">{t`The receipt could not be opened. Access may have changed or its bytes may have expired. Reload to check.`}</p> : null}
    {url ? <><p className="text-sm text-muted">{t`Private preview closes when you leave this view. Only download to an approved finance location.`}</p>
      {receipt.mime === "application/pdf" ? <iframe className="h-96 w-full rounded-xl border border-line" title={t`Receipt ${receipt.id} preview`} sandbox="" src={url} />
        : ["image/jpeg", "image/png"].includes(receipt.mime) ? <img className="max-h-96 max-w-full object-contain" src={url} alt={t`Receipt ${receipt.id}`} />
          : <p>{t`HEIC previews are not supported by every browser. Download to inspect this receipt.`}</p>}
      <a className="desk-button min-h-11" href={url} download={`finance-receipt-${receipt.id}.${extension}`}>{t`Download private receipt`}</a>
      <button type="button" className="desk-button min-h-11" onClick={() => {
        if (liveUrl.current) URL.revokeObjectURL(liveUrl.current); liveUrl.current = null; setUrl(null);
      }}>{t`Close receipt`}</button></> : null}
  </article>;
}
