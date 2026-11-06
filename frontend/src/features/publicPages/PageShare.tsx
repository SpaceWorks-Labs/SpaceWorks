import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Copy, Download, QrCode } from "lucide-react";
import writerWasmUrl from "zxing-wasm/writer/zxing_writer.wasm?url";
import { SocialCardPreview } from "./SocialCardPreview";

export function PageShare({ title, description = "", canonicalUrl, image }: {
  title: string; description?: string; canonicalUrl: string; image?: React.ReactNode;
}) {
  const [qrOpen, setQrOpen] = useState(false);
  const [qr, setQr] = useState<{ url: string; value: string } | null>(null);
  const [message, setMessage] = useState("");
  const [qrError, setQrError] = useState("");
  useEffect(() => {
    if (!qrOpen) return;
    let active = true; let objectUrl: string | undefined;
    setQr(null); setQrError("");
    void import("zxing-wasm/writer").then(async writer => {
      writer.setZXingModuleOverrides({ locateFile: () => writerWasmUrl });
      const result = await writer.writeBarcode(canonicalUrl, { format: "QRCode", scale: 6, addQuietZones: true });
      if (!result.image) throw new Error(t`QR image unavailable`);
      if (active) { objectUrl = URL.createObjectURL(result.image); setQr({ url: objectUrl, value: canonicalUrl }); }
    }).catch(() => { if (active) setQrError(t`Couldn't create the QR image. Use the page link below.`); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [qrOpen, canonicalUrl]);
  return <section aria-label={t`Share this page`} className="grid min-w-0 gap-3 rounded-xl border border-line bg-panel p-4">
    <h2 className="title-section">{t`Share this page`}</h2>
    <SocialCardPreview title={title} description={description} url={canonicalUrl} image={image} />
    <a className="min-h-11 break-all py-2 text-sm text-brand-ink underline" href={canonicalUrl}>{canonicalUrl}</a>
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button" onClick={() => { void Promise.resolve().then(() => navigator.clipboard.writeText(canonicalUrl)).then(() => setMessage(t`Page link copied.`)).catch(() => setMessage(t`Couldn't copy. Select the page link above to copy it.`)); }}><Copy size={20} aria-hidden="true" />{t`Copy link`}</button>
      <button type="button" className="desk-button" aria-expanded={qrOpen} onClick={() => setQrOpen(value => !value)}><QrCode size={20} aria-hidden="true" />{qrOpen ? t`Hide QR code` : t`Show QR code`}</button>
    </div>
    <p role="status" className="text-sm text-muted">{message}</p>
    {qrOpen ? <div className="grid justify-items-start gap-2">
      {qr?.value === canonicalUrl ? <><img src={qr.url} alt={t`QR code linking to ${title}`} width={240} height={240} className="max-w-full" />
        <a className="desk-button" href={qr.url} download="space-works-page-qr.png"><Download size={20} aria-hidden="true" />{t`Download QR PNG`}</a></> : qrError ? <p role="alert" className="text-sm text-danger">{qrError}</p> : <p role="status">{t`Creating QR code…`}</p>}
      <p className="text-sm text-muted">{t`This QR opens the public page URL.`}</p>
    </div> : null}
  </section>;
}
