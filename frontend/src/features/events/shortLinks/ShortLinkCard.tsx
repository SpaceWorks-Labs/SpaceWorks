import { useEffect, useState } from "react";
import { Copy, Download, Link, QrCode, RefreshCw } from "lucide-react";
import writerWasmUrl from "zxing-wasm/writer/zxing_writer.wasm?url";
import { ConfirmDialog, Skeleton } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { eventErrorText } from "../../staff/eventUi";
import { useCreateShortLink, useRegenerateShortLink, useShortLink, type ShortLinkVisitDay } from "./shortLinkApi";

/** Decorative 30-day sparkline; the visible total carries the information. */
export function VisitSparkline({ days }: { days: ShortLinkVisitDay[] }) {
  const max = Math.max(1, ...days.map(day => day.count));
  const step = days.length > 1 ? 120 / (days.length - 1) : 0;
  const points = days.map((day, index) => `${(index * step).toFixed(1)},${(28 - (day.count / max) * 26).toFixed(1)}`).join(" ");
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 120 30" className="h-8 w-32 text-brand">
    <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
  </svg>;
}

function useQrImage(value: string | null, open: boolean) {
  const [image, setImage] = useState<{ url: string; value: string } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open || !value) return;
    let active = true; let objectUrl: string | undefined;
    setImage(null); setError("");
    void import("zxing-wasm/writer").then(async writer => {
      writer.setZXingModuleOverrides({ locateFile: () => writerWasmUrl });
      const result = await writer.writeBarcode(value, { format: "QRCode", scale: 6, addQuietZones: true });
      if (!result.image) throw new Error("QR image unavailable");
      if (active) { objectUrl = URL.createObjectURL(result.image); setImage({ url: objectUrl, value }); }
    }).catch(() => { if (active) setError("Couldn't create the QR image. Copy the link instead."); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [open, value]);
  return { image: image?.value === value ? image.url : null, error };
}

/** The event's short /e/<code> link: copy, QR, regenerate (with a confirm) and 30-day visits. */
export function ShortLinkCard({ eventId, published }: { eventId: number; published: boolean }) {
  const query = useShortLink(eventId);
  const create = useCreateShortLink(eventId);
  const regenerate = useRegenerateShortLink(eventId);
  const [confirming, setConfirming] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [message, setMessage] = useState("");
  const link = query.data;
  const qr = useQrImage(link?.url ?? null, qrOpen);
  const error = create.error ?? regenerate.error ?? query.error;
  // Off for this space (events.short_links): the card is not offered at all.
  if (query.error instanceof StructuredApiError && query.error.status === 404) return null;
  return <section aria-labelledby={`short-link-${eventId}`} className="grid min-w-0 gap-3 rounded-xl border border-line bg-panel p-4">
    <h3 id={`short-link-${eventId}`} className="title-section flex items-center gap-2"><Link aria-hidden="true" size={18} />Short link</h3>
    {query.isLoading ? <Skeleton className="h-16 w-full" /> : null}
    {error ? <p role="alert" className="text-sm text-danger">{eventErrorText(error)}</p> : null}
    {link && !link.url ? <div className="grid gap-2">
      <p className="text-sm text-muted">{published ? "Make a short link to put on posters and chats. It always opens this event." : "Publish the event first; a short link only opens a published event."}</p>
      <button type="button" className="desk-button justify-self-start" disabled={!published || create.isPending} onClick={() => create.mutate()}>{create.isPending ? "Making link…" : "Create short link"}</button>
    </div> : null}
    {link?.url ? <div className="grid gap-3">
      <a className="min-h-11 break-all py-2 font-semibold text-brand-ink underline" href={link.url}>{link.url}</a>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" onClick={() => { void Promise.resolve().then(() => navigator.clipboard.writeText(link.url ?? "")).then(() => setMessage("Short link copied.")).catch(() => setMessage("Couldn't copy. Select the link above to copy it.")); }}><Copy size={20} aria-hidden="true" />Copy link</button>
        <button type="button" className="desk-button" aria-expanded={qrOpen} onClick={() => setQrOpen(open => !open)}><QrCode size={20} aria-hidden="true" />{qrOpen ? "Hide QR code" : "Show QR code"}</button>
        <button type="button" className="desk-button" onClick={() => setConfirming(true)}><RefreshCw size={20} aria-hidden="true" />Make a new link</button>
      </div>
      <p role="status" className="text-sm text-muted">{message}</p>
      {qrOpen ? <div className="grid justify-items-start gap-2">
        {qr.image ? <><img src={qr.image} alt={`QR code for ${link.url}`} width={200} height={200} className="max-w-full" />
          <a className="desk-button" href={qr.image} download="event-short-link-qr.png"><Download size={20} aria-hidden="true" />Download QR PNG</a></>
          : qr.error ? <p role="alert" className="text-sm text-danger">{qr.error}</p> : <p role="status">Creating QR code…</p>}
      </div> : null}
      <div className="flex flex-wrap items-center gap-3">
        <VisitSparkline days={link.visits_30d} />
        <p className="text-sm"><span className="font-semibold tabular-nums">{link.visits_30d.reduce((sum, day) => sum + day.count, 0)}</span> visits in the last 30 days · <span className="tabular-nums">{link.total_visits}</span> in total</p>
      </div>
      <p className="text-xs text-muted">Visits are counted without storing who visited.</p>
    </div> : null}
    <ConfirmDialog open={confirming} tone="danger" title="Make a new short link?" message="The old link stops working straight away."
      confirmLabel="Make new link" pending={regenerate.isPending} onCancel={() => setConfirming(false)}
      onConfirm={() => regenerate.mutate(undefined, { onSettled: () => setConfirming(false) })} />
  </section>;
}
