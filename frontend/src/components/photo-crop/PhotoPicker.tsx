// Take a photo with the camera or choose a file, then crop it to the card's photo frame.
// The cropped picture (a JPEG) is what the caller uploads; the original never leaves the browser.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { CameraCapture } from "../ui/CameraCapture";
import { PhotoCropDialog } from "./PhotoCropDialog";
import { BoxArt } from "../BoxSpinner";

export const PHOTO_TYPES = "image/png,image/jpeg,image/webp";

export function PhotoPicker({ aspect, disabled = false, busy = false, onPhoto, chooseLabel = "Choose a photo" }: {
  aspect: number; disabled?: boolean; busy?: boolean; onPhoto: (cropped: Blob) => void; chooseLabel?: string;
}) {
  const [camera, setCamera] = useState(false);
  const [picked, setPicked] = useState<Blob | null>(null);
  const off = disabled || busy;
  return <div className="flex flex-wrap items-center gap-2">
    <label className={`desk-button min-h-11 cursor-pointer focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus ${off ? "pointer-events-none opacity-60" : ""}`}>
      {busy ? <><BoxArt size={16} mono />{t`Uploading…`}</> : chooseLabel}
      <input type="file" accept={PHOTO_TYPES} className="sr-only" disabled={off}
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) setPicked(file); }} />
    </label>
    <button type="button" className="desk-button-ghost min-h-11" disabled={off} onClick={() => setCamera(true)}>{t`Take a photo`}</button>
    <CameraCapture open={camera} label={t`Card photo`} onClose={() => setCamera(false)}
      onCapture={(file) => { setCamera(false); setPicked(file); }} />
    <PhotoCropDialog file={picked} aspect={aspect} onCancel={() => setPicked(null)}
      onDone={(cropped) => { setPicked(null); onPhoto(cropped); }} />
  </div>;
}
