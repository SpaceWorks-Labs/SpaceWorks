import { t } from "@lingui/core/macro";
import { useEffect, useId, useState } from "react";

import { PhotoCropDialog } from "../../../components/photo-crop/PhotoCropDialog";

// The Classic member card's photo frame (18 x 22 mm), as on the member's own card photo.
const PHOTO_ASPECT = 18 / 22;

/**
 * The join form's card photo (parity O-B2): choose, crop to the card's photo frame, and agree to it
 * being stored. Nothing uploads until the form is sent, and only with the box ticked, so a photo the
 * applicant did not agree to never reaches storage. It never replaces a photo a card already has.
 */
export function JoinPhotoField({ required, file, consent, onFile, onConsent, error, onFileNote }: {
  required: boolean; file: File | null; consent: boolean; onFile: (file: File | null) => void; onConsent: (consent: boolean) => void;
  error?: string; onFileNote?: string;
}) {
  const inputId = useId();
  const consentId = useId();
  const errorId = useId();
  const [cropping, setCropping] = useState<File | null>(null);
  const [cropped, setCropped] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return <fieldset className="grid min-w-0 gap-3 rounded-2xl border border-line bg-panel p-4" aria-describedby={error ? errorId : undefined}>
    <legend className="px-1 text-sm font-semibold text-ink">{required ? t`Your photo (required)` : t`Your photo (optional)`}</legend>
    <p className="text-sm text-muted">{t`It prints on your member card so staff can recognise you. Use a clear photo of your face.`}</p>
    {onFileNote ? <p className="text-sm text-muted">{onFileNote}</p> : null}
    <div className="flex flex-wrap items-start gap-4">
      {preview ? <img src={preview} alt={t`Your chosen photo`} className="h-28 w-[92px] shrink-0 rounded-lg border border-line object-cover" /> : null}
      <div className="grid min-w-0 flex-1 basis-56 gap-2">
        <label className="text-sm font-medium text-ink" htmlFor={inputId}>{file ? t`Choose a different photo` : t`Choose a photo`}</label>
        <input id={inputId} type="file" accept="image/jpeg,image/png,image/webp" aria-invalid={Boolean(error)}
          onChange={(event) => { onFile(event.target.files?.[0] ?? null); setCropped(false); }}
          className="block w-full min-w-0 text-sm text-muted file:mr-3 file:min-h-11 file:rounded-md file:border-0 file:bg-accent file:px-3 file:py-2 file:text-sm file:font-semibold file:text-on-accent" />
        {file ? <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <span>{cropped ? t`Cropped to the card's photo spot.` : t`Crop it so your face fills the card's photo spot.`}</span>
          <button className="desk-button-ghost min-h-11" type="button" onClick={() => setCropping(file)}>{cropped ? t`Crop again` : t`Crop the photo`}</button>
          <button className="desk-button-ghost min-h-11" type="button" onClick={() => { onFile(null); onConsent(false); }}>{t`Remove`}</button>
        </div> : null}
      </div>
    </div>
    <PhotoCropDialog file={cropping} aspect={PHOTO_ASPECT} onCancel={() => setCropping(null)}
      onDone={(blob) => { setCropping(null); setCropped(true); onFile(new File([blob], "join-photo.jpg", { type: blob.type || "image/jpeg" })); }} />
    {file ? <label className="flex items-start gap-3 text-sm text-ink" htmlFor={consentId}>
      <input id={consentId} type="checkbox" className="mt-0.5 h-5 w-5 shrink-0" checked={consent} onChange={(event) => onConsent(event.target.checked)} />
      <span>{t`I agree to my photo being stored privately for my member card and for staff to check it at the door. It is never shown publicly.`}</span>
    </label> : null}
    {error ? <p id={errorId} role="alert" className="text-sm text-danger">{error}</p> : null}
  </fieldset>;
}
