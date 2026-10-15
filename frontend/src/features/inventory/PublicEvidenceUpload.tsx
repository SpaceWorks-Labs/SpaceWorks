import { useEffect, useState } from "react";
import { Camera, CircleCheck, ImageUp } from "lucide-react";

import { CameraCapture } from "../../components/ui";
import {
  requestPublicEvidenceUpload,
  uploadPublicEvidenceFile,
} from "./selfCheckoutApi";

export function PublicEvidenceUpload({
  slug,
  evidenceType,
  disabled = false,
  onUploaded,
}: {
  slug: string;
  evidenceType: "issue" | "return";
  disabled?: boolean;
  onUploaded: (evidenceId: number | null) => void;
}) {
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraSupported] = useState(
    () => typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia,
  );
  const label = evidenceType === "issue" ? "Issue photo" : "Return photo";
  const busy = disabled || status === "uploading";

  useEffect(() => {
    setStatus("idle");
    setError("");
    setFileName("");
    setCameraOpen(false);
    onUploaded(null);
  }, [evidenceType, onUploaded]);

  async function handleFile(file: File) {
    setStatus("uploading");
    setError("");
    setFileName(file.name);
    onUploaded(null);
    try {
      const presigned = await requestPublicEvidenceUpload(slug, {
        evidence_type: evidenceType,
        content_type: file.type,
        size_bytes: file.size,
      });
      await uploadPublicEvidenceFile(presigned, file);
      setStatus("done");
      onUploaded(presigned.evidence_id);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Upload failed.");
      onUploaded(null);
    }
  }

  // Two full-width rows, never side by side: a native file input squeezed beside a button collapses
  // into a sliver of its "Choose file" swatch in a narrow panel. The input itself stays the labelled,
  // focusable control; the visible button is its <label>, so a tap anywhere on it opens the picker.
  return (
    <div className="grid min-w-0 gap-2">
      <p className="text-sm font-semibold text-ink">{label}</p>
      {cameraSupported ? (
        <button className="desk-button w-full" type="button" aria-label={`Take ${label}`} disabled={busy} onClick={() => setCameraOpen(true)}>
          <Camera aria-hidden="true" size={18} />
          {status === "done" ? "Retake with camera" : "Take photo with camera"}
        </button>
      ) : null}
      <label className={`desk-button w-full cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${busy ? "pointer-events-none border-line bg-surface text-muted" : ""}`}>
        <ImageUp aria-hidden="true" size={18} />
        <span className="min-w-0 truncate">{status === "done" ? "Choose another file" : cameraSupported ? "Choose a file instead" : "Choose file"}</span>
        <input
          aria-label={label}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) handleFile(file);
          }}
          className="sr-only"
        />
      </label>
      <CameraCapture open={cameraOpen} onClose={() => setCameraOpen(false)} onCapture={(file) => { void handleFile(file); }} label={label} />
      {/* ONE persistent live region, not three conditional ones: a role="status" element that is
          inserted at the same moment its text appears is frequently not announced, because the
          region was not in the DOM for the screen reader to observe changing. */}
      <p
        role="status"
        aria-live="polite"
        className={`flex min-w-0 items-center gap-2 text-sm [overflow-wrap:anywhere] ${status === "error" ? "text-danger" : status === "done" ? "font-semibold text-success-ink" : "text-muted"}`}
      >
        {status === "uploading"
          ? `Uploading ${fileName}...`
          : status === "done"
            ? <><CircleCheck aria-hidden="true" size={16} className="shrink-0" />Photo uploaded</>
            : status === "error"
              ? error
              : ""}
      </p>
    </div>
  );
}
