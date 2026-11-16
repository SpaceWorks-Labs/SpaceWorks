import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Modal } from "../../../components/ui";

/** The member card QR at scanning size.
 *
 *  The ticket's QR is a fixed thumbnail, too small for some desk scanners on a phone held at
 *  arm's length. This view sizes the same image to the screen: the full dialog width in
 *  portrait, and the viewport height in landscape so the whole code stays on screen. The PNG
 *  carries its own white quiet zone, so it scans the same in dark mode. */
export function ScanQrView({ src, name }: { src: string; name: string }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className="desk-button-brand w-full sm:w-auto" onClick={() => setOpen(true)}>{t`Show QR to scan`}</button>
    <Modal open={open} title={t`Scan your member card`} onClose={() => setOpen(false)}
      footer={<button type="button" className="desk-button w-full" onClick={() => setOpen(false)}>{t`Done`}</button>}>
      <div className="grid justify-items-center gap-3">
        <img src={src} alt={t`Member card QR code for ${name}`}
          className="aspect-square w-full max-w-[min(100%,28rem,calc(100dvh-12rem))] rounded-xl [image-rendering:pixelated]" />
        <p className="break-words text-center font-semibold text-ink [@media(max-height:500px)]:sr-only">{name}</p>
        <p className="max-w-prose text-center text-sm text-muted [@media(max-height:500px)]:hidden">{t`Hold your phone flat under the scanner. Turn your screen brightness up if it does not read.`}</p>
      </div>
    </Modal>
  </>;
}
