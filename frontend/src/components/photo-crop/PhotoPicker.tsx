// Take a photo with the camera or choose a file, then crop it to the card's photo frame.
// The cropped picture (a JPEG) is what the caller uploads; the original never leaves the browser.
import { useState } from "react";

import { CameraCapture } from "../ui/CameraCapture";
import { PhotoCropDialog } from "./PhotoCropDialog";

export const PHOTO_TYPES = "image/png,image/jpeg,image/webp";

export function PhotoPicker({ aspect, disabled = false, busy = false, onPhoto, chooseLabel = "Choose a photo" }: {
  aspect: number; disabled?: boolean; busy?: boolean; onPhoto: (cropped: Blob) => void; chooseLabel?: string;
}) {
  const [camera, setCamera] = useState(false);
  const [picked, setPicked] = useState<Blob | null>(null);
  const off = disabled || busy;
  return <div className="flex flex-wrap items-center gap-2">
    <label className={`desk-button min-h-11 cursor-pointer ${off ? "pointer-events-none opacity-60" : ""}`}>
      {busy ? "Uploading…" : chooseLabel}
      <input type="file" accept={PHOTO_TYPES} className="sr-only" disabled={off}
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) setPicked(file); }} />
    </label>
    <button type="button" className="desk-button-ghost min-h-11" disabled={off} onClick={() => setCamera(true)}>Take a photo</button>
    <CameraCapture open={camera} label="Card photo" onClose={() => setCamera(false)}
      onCapture={(file) => { setCamera(false); setPicked(file); }} />
    <PhotoCropDialog file={picked} aspect={aspect} onCancel={() => setPicked(null)}
      onDone={(cropped) => { setPicked(null); onPhoto(cropped); }} />
  </div>;
}
