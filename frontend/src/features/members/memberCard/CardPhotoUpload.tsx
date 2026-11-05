import { useId, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { PhotoCropDialog } from "../../../components/photo-crop/PhotoCropDialog";
import { memberCardKey, uploadCardPhoto, useDeleteCardPhoto } from "./api";

// The Classic member card's photo frame (18 x 22 mm); My cards uses the live design's frame.
const PHOTO_ASPECT = 18 / 22;

const CONSENT_TEXT =
  "I agree to my photo being stored privately for staff to check my card at the door. It is never shown publicly, and it is deleted when this card is revoked.";

/** The member's own card photo.
 *
 *  Consent gates the whole flow, not just the final attach: without the tick nothing is
 *  presigned and nothing reaches the bucket, so an un-consented photo never exists.
 */
export function CardPhotoUpload({
  makerspaceId,
  photoSet,
  consentAt,
}: {
  makerspaceId: number;
  photoSet: boolean;
  consentAt: string | null;
}) {
  const client = useQueryClient();
  const inputId = useId();
  const consentId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [cropping, setCropping] = useState<File | null>(null);
  const [cropped, setCropped] = useState(false);
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const remove = useDeleteCardPhoto(makerspaceId);

  async function upload() {
    if (!file) {
      setStatus("error");
      setError("Choose a photo first.");
      return;
    }
    if (!consent) {
      setStatus("error");
      setError("Tick the consent box before uploading your photo.");
      return;
    }
    setStatus("uploading");
    setError("");
    try {
      await uploadCardPhoto(makerspaceId, file);
      setStatus("done");
      setFile(null);
      await client.invalidateQueries({ queryKey: memberCardKey(makerspaceId) });
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-line p-3">
      <h3 className="title-section">Card photo</h3>
      <p className="mt-1 text-sm text-muted">
        {photoSet
          ? consentAt
            ? `Photo on file since ${new Date(consentAt).toLocaleDateString()}.`
            : "Photo on file."
          : "No photo on file yet."}
      </p>

      <label className="mt-3 block text-sm font-medium text-ink" htmlFor={inputId}>
        Choose a photo
      </label>
      <input
        id={inputId}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        disabled={status === "uploading"}
        onChange={(event) => { setFile(event.target.files?.[0] ?? null); setCropped(false); }}
        className="mt-1 block w-full min-w-0 text-sm text-muted file:mr-3 file:min-h-11 file:rounded-md file:border-0 file:bg-accent file:px-3 file:py-2 file:text-sm file:font-semibold file:text-on-accent"
      />

      {file ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>{cropped ? "Cropped to the card's photo spot." : "Crop it so your face fills the card's photo spot."}</span>
          <button className="desk-button-ghost min-h-11" type="button" onClick={() => setCropping(file)}>
            {cropped ? "Crop again" : "Crop the photo"}
          </button>
        </div>
      ) : null}
      <PhotoCropDialog file={cropping} aspect={PHOTO_ASPECT} onCancel={() => setCropping(null)}
        onDone={(blob) => { setCropping(null); setCropped(true);
          setFile(new File([blob], "card-photo.jpg", { type: blob.type || "image/jpeg" })); }} />

      <label className="mt-3 flex items-start gap-3 text-sm text-ink" htmlFor={consentId}>
        <input
          id={consentId}
          type="checkbox"
          className="mt-0.5 h-5 w-5 shrink-0"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
        />
        <span>{CONSENT_TEXT}</span>
      </label>

      <div className="desk-actions mt-3 flex flex-wrap gap-2 [&>button]:flex-1 sm:[&>button]:flex-none">
        <button
          className="desk-button-brand"
          type="button"
          disabled={status === "uploading"}
          onClick={() => void upload()}
        >
          {status === "uploading" ? "Uploading…" : "Upload photo"}
        </button>
        {photoSet ? (
          <button
            className="desk-button-ghost text-danger"
            type="button"
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            {remove.isPending ? "Removing…" : "Remove photo"}
          </button>
        ) : null}
      </div>

      {/* ONE persistent live region, not several conditional ones: a role="status" element
          inserted at the same moment its text appears is frequently not announced. */}
      <p
        role="status"
        aria-live="polite"
        className={`mt-2 text-xs ${status === "error" ? "text-danger" : "text-muted"}`}
      >
        {status === "uploading"
          ? "Uploading your photo…"
          : status === "done"
            ? "Photo uploaded."
            : status === "error"
              ? error
              : ""}
      </p>
      {remove.error ? (
        <p className="mt-1 text-xs text-danger" role="alert">
          {remove.error instanceof Error ? remove.error.message : "Could not remove the photo."}
        </p>
      ) : null}
    </div>
  );
}
