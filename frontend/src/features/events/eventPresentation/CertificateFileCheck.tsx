import { t } from "@lingui/core/macro";
import { useState, type DragEvent } from "react";
import { FileCheck2, FileX2, Upload } from "lucide-react";

/** SHA-256 of a file, as lowercase hex, computed in the browser. The file never leaves the device. */
export async function sha256Hex(file: Blob) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export const shortFingerprint = (hex: string) => hex.slice(0, 16).toUpperCase().match(/.{4}/g)?.join(" ") ?? "";

/** Drop or choose the PDF you were given; it is compared with the issued file's fingerprint. */
export function CertificateFileCheck({ expected }: { expected: string }) {
  const [state, setState] = useState<{ status: "idle" | "checking" | "match" | "mismatch" | "error"; name?: string }>({ status: "idle" });
  const [dragging, setDragging] = useState(false);
  async function check(file?: File | null) {
    if (!file) return;
    setState({ status: "checking", name: file.name });
    try { setState({ status: (await sha256Hex(file)) === expected.toLowerCase() ? "match" : "mismatch", name: file.name }); }
    catch { setState({ status: "error", name: file.name }); }
  }
  const drop = (event: DragEvent) => { event.preventDefault(); setDragging(false); void check(event.dataTransfer.files?.[0]); };
  return <section className="grid gap-3" aria-labelledby="file-check">
    <h2 id="file-check" className="text-base font-semibold text-ink">{t`Check a certificate file`}</h2>
    <p className="text-sm text-muted">{t`Someone sent you this certificate as a PDF? Check it here. The file is read on your device and is never uploaded.`}</p>
    <label onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}
      className={`grid min-h-28 cursor-pointer place-items-center gap-2 rounded-control border-2 border-dashed p-4 text-center text-sm focus-within:outline-2 focus-within:outline-focus ${dragging ? "border-focus bg-panel" : "border-line"}`}>
      <Upload size={20} aria-hidden="true" className="text-muted" />
      <span className="text-ink">{t`Drop the PDF here or `}<span className="font-semibold underline">{t`choose a file`}</span></span>
      <input type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(event) => { void check(event.target.files?.[0]); event.target.value = ""; }} />
    </label>
    <div aria-live="polite">
      {state.status === "checking" ? <p className="text-sm text-muted">{t`Checking `}{state.name}…</p> : null}
      {state.status === "match" ? <p className="flex items-start gap-2 rounded-control border border-success bg-success-soft p-3 text-sm text-success-ink">
        <FileCheck2 size={18} aria-hidden="true" className="mt-0.5 shrink-0" /><span><strong>{t`This file matches the issued certificate.`}</strong> {t` It has not been changed since it was issued.`}</span></p> : null}
      {state.status === "mismatch" ? <p className="flex items-start gap-2 rounded-control border border-danger-line bg-panel p-3 text-sm text-danger">
        <FileX2 size={18} aria-hidden="true" className="mt-0.5 shrink-0" /><span><strong>{t`This file does not match.`}</strong> {t` It is not the PDF that was issued for this certificate, or it was changed afterwards.`}</span></p> : null}
      {state.status === "error" ? <p className="text-sm text-danger">{t`This browser could not read the file. Try another browser.`}</p> : null}
    </div>
  </section>;
}
