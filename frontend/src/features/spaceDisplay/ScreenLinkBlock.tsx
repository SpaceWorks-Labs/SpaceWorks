import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import writerWasmUrl from "zxing-wasm/writer/zxing_writer.wasm?url";
import { ActionControl } from "../../components/ui";
import type { AdminDisplay } from "./api";

/** How long Anthias should show this page: one full pass of the playlist, so no slide is cut off. */
export function suggestedSeconds(row: Pick<AdminDisplay, "layout" | "panels" | "slide_seconds" | "rotation_seconds">): number {
  if (row.layout !== "playlist") return 60;
  const total = row.panels.reduce((sum, panel) => sum + (row.slide_seconds[panel] ?? row.rotation_seconds), 0);
  return Math.max(10, Math.min(3600, total));
}

function useQrImage(value: string, open: boolean) {
  const [image, setImage] = useState<{ url: string; value: string } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!open || !value) return;
    let active = true; let objectUrl: string | undefined;
    setFailed(false);
    void import("zxing-wasm/writer").then(async (writer) => {
      writer.setZXingModuleOverrides({ locateFile: () => writerWasmUrl });
      const result = await writer.writeBarcode(value, { format: "QRCode", scale: 5, addQuietZones: true });
      if (!result.image) throw new Error(t`QR image unavailable`);
      if (active) { objectUrl = URL.createObjectURL(result.image); setImage({ url: objectUrl, value }); }
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [open, value]);
  return { src: image?.value === value ? image.url : null, failed };
}

/**
 * "Use with Anthias" for one screen: the address (it carries the screen's secret, so treat it like a
 * password), a copy button, a QR to open it on a phone, and the duration to give the asset. The server
 * returns the address only when it is made or replaced (L-D3), so `url` is empty once the page reloads:
 * then the block says so and offers New address instead.
 */
export function ScreenLinkBlock({ row, url, busy, onRotate }: { row: AdminDisplay; url: string; busy: boolean; onRotate: () => void }) {
  const [copied, setCopied] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const qr = useQrImage(url, qrOpen);
  const copy = async () => { try { await navigator.clipboard.writeText(url); setCopied(true); } catch { setCopied(false); } };
  return <div className="grid gap-2 rounded-lg border border-line p-3">
    <p className="text-sm font-semibold text-ink">{t`Use with Anthias`}</p>
    {url ? <>
      <p className="text-xs text-muted">{t`Add this address as a web asset. Anyone who has it can see this screen, so share it like a password. It is shown only now.`}</p>
      <input readOnly className="desk-input font-mono text-xs" aria-label={t`Screen address`} value={url} onFocus={(e) => e.currentTarget.select()} />
    </> : <p className="text-xs text-muted">{t`The address is shown only when it is made. If you no longer have it, make a new address; the old one stops working.`}</p>}
    <p className="text-sm">{t`Suggested duration: ${suggestedSeconds(row)} seconds`}</p>
    <div className="flex flex-wrap gap-2">
      {url ? <ActionControl action={{ label: copied ? t`Copied` : t`Copy address`, onClick: () => void copy() }} /> : null}
      {url ? <ActionControl action={{ label: qrOpen ? t`Hide QR` : t`Show QR`, onClick: () => setQrOpen(!qrOpen) }} /> : null}
      <ActionControl action={{ label: t`New address`, pending: busy, onClick: onRotate,
        confirm: { title: t`Replace this address?`, message: t`The old address stops working. Players you chose below are updated automatically; a player you added by hand needs the new address.`, confirmLabel: t`Replace` } }} />
    </div>
    {url && qrOpen ? (qr.src ? <img src={qr.src} alt={t`QR code for the screen address`} className="h-40 w-40" />
      : <p className="text-xs text-muted" role="status">{qr.failed ? t`Couldn't make the QR. Copy the address instead.` : t`Making QR…`}</p>) : null}
  </div>;
}
