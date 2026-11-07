import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import writerWasmUrl from "zxing-wasm/writer/zxing_writer.wasm?url";

/** A QR image for `value`, drawn in the browser; nothing is sent anywhere. */
function useQrImage(value: string, open: boolean) {
  const [image, setImage] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    let active = true; let objectUrl: string | undefined;
    setImage(null); setError("");
    void import("zxing-wasm/writer").then(async writer => {
      writer.setZXingModuleOverrides({ locateFile: () => writerWasmUrl });
      const result = await writer.writeBarcode(value, { format: "QRCode", scale: 6, addQuietZones: true });
      if (!result.image) throw new Error(t`QR image unavailable`);
      if (active) { objectUrl = URL.createObjectURL(result.image); setImage(objectUrl); }
    }).catch(() => { if (active) setError(t`Couldn't draw the QR. Print the link instead.`); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [open, value]);
  return { image, error };
}

/** The machine's session QR: members scan it to open "Use this machine" for this machine. */
export function SessionQrCard({ machineId, machineName, basePath }: { machineId: number; machineName: string; basePath: string }) {
  const [open, setOpen] = useState(false);
  const link = `${window.location.origin}${basePath}/machines/${machineId}/use`;
  const qr = useQrImage(link, open);
  return <section className="grid gap-2 rounded-xl border border-line p-3" aria-labelledby={`session-qr-${machineId}`}>
    <h3 id={`session-qr-${machineId}`} className="title-section">{t`Session QR`}</h3>
    <p className="text-sm text-muted">{t`Stick it on the machine. Members scan it to start and stop their session.`}</p>
    <p className="text-sm [overflow-wrap:anywhere]"><a className="underline" href={link}>{link}</a></p>
    {open ? qr.image ? <img className="w-48 rounded-md border border-line bg-white p-2" src={qr.image} alt={t`Session QR for ${machineName}`} />
      : <p role="status" className="text-sm text-muted">{qr.error || t`Drawing the QR…`}</p> : null}
    <button type="button" className="desk-button w-fit" onClick={() => setOpen(current => !current)}>{open ? t`Hide QR` : t`Show QR`}</button>
  </section>;
}
