import { useEffect, useMemo, useState } from "react";
import writerWasmUrl from "zxing-wasm/writer/zxing_writer.wasm?url";
import { CardLayerView, type LiveImages } from "../../components/card-designer/CardLayerView";
import {
  CARD_H, CARD_W, SAMPLE_LOGO_RADIUS_MM, SAMPLE_PHOTO, SAMPLE_QR_TARGET, sampleHolder, sampleIdCardFront,
} from "./idCardSample";

/** A real, scannable QR for the sample card, drawn in the browser with the same writer the app uses. */
function useSampleQr(value: string) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let active = true; let objectUrl: string | undefined;
    void import("zxing-wasm/writer").then(async writer => {
      writer.setZXingModuleOverrides({ locateFile: () => writerWasmUrl });
      const result = await writer.writeBarcode(value, { format: "QRCode", scale: 6, addQuietZones: true });
      if (result.image && active) { objectUrl = URL.createObjectURL(result.image); setUrl(objectUrl); }
    }).catch(() => { /* decorative: the renderer's placeholder pattern stays */ });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [value]);
  return url;
}

/**
 * A sample staff ID card drawn by the real card renderer (CardLayerView), the way the designer and the
 * printed-card view draw one. Decorative: hidden from assistive tech, no pointer events. The number comes
 * from the card numbering generator; the QR is real and scannable (the owner's sample target).
 */
export function SampleIdCard({ width = 360 }: { width?: number }) {
  const side = useMemo(() => sampleIdCardFront(), []);
  const values = useMemo(() => sampleHolder(), []);
  const qr = useSampleQr(SAMPLE_QR_TARGET);
  const live: LiveImages = { photo: SAMPLE_PHOTO, logos: { space: "/brand/icon-192.png" }, assets: {}, desk_qr: null, verify_qr: qr };
  const px = width / CARD_W;
  return <div aria-hidden="true" data-sample-id-card=""
    className="pointer-events-none relative select-none overflow-hidden rounded-[3.18mm]"
    style={{ width, height: CARD_H * px, background: side.background.kind === "colour" ? side.background.colour : undefined }}>
    {side.layers.map(layer => <div key={layer.id} className="absolute" data-layer-kind={layer.kind}
      style={{ left: layer.x_mm * px, top: layer.y_mm * px, width: layer.w_mm * px, height: layer.h_mm * px,
        ...(layer.kind === "logo" ? { borderRadius: SAMPLE_LOGO_RADIUS_MM * px, overflow: "hidden" } : {}) }}>
      <CardLayerView layer={layer} px={px} values={values} designId={0} mono={false} live={live} />
    </div>)}
  </div>;
}
