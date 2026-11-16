// One person's real badge for the check-in desk. Structured designs draw through E-F1's BadgeCanvas (no
// interaction); free-canvas designs draw their compiled document layers through the card designer's
// CardLayerView. The QR is generated in the browser from the check-in payload, so nothing here needs the network.
import { CardLayerView } from "../../../components/card-designer/CardLayerView";
import type { Layer } from "../../../components/card-designer/cardTypes";
import { BadgeCanvas, useQrImage } from "./BadgeCanvas";
import { badgeValues, type DeskBadge, type DeskBundle, type DeskDesign } from "./deskBadgeApi";

export function deskSize(design: DeskDesign) {
  return { widthMm: design.document.front.page_width_mm, heightMm: design.document.front.page_height_mm };
}

function FreeCanvasFace({ badge, design, logos, pxPerMm }: { badge: DeskBadge; design: DeskDesign; logos: DeskBundle["logos"]; pxPerMm: number }) {
  const { widthMm, heightMm } = deskSize(design);
  const front = design.document.front;
  const qr = useQrImage(badge.checkin_payload);
  const values = badgeValues(badge);
  const live = { photo: badge.photo ?? null, logos, assets: design.assets ?? {}, desk_qr: null, verify_qr: null };
  return <div data-badge-preview="" className="relative shrink-0 select-none overflow-hidden"
    style={{ width: widthMm * pxPerMm, height: heightMm * pxPerMm, background: front.background?.colour ?? "#FFFFFF",
      printColorAdjust: "exact", WebkitPrintColorAdjust: "exact", outline: "1px solid rgb(20 44 42 / 14%)" }}>
    {front.layers.map((layer) => <div key={layer.id} aria-hidden="true" className="absolute"
      style={{ left: layer.x_mm * pxPerMm, top: layer.y_mm * pxPerMm, width: layer.w_mm * pxPerMm, height: layer.h_mm * pxPerMm }}>
      {layer.kind === "checkin_qr" ? (qr ? <img src={qr} alt="" className="h-full w-full bg-white" style={{ imageRendering: "pixelated" }} /> : null)
        : <CardLayerView layer={layer as unknown as Layer} px={pxPerMm} values={values} designId={design.design_id}
          mono={Boolean(design.document.mono)} live={live} />}
    </div>)}
  </div>;
}

export function DeskBadgeFace({ badge, design, logos, pxPerMm }: { badge: DeskBadge; design: DeskDesign; logos: DeskBundle["logos"]; pxPerMm: number }) {
  if (!design.settings) return <FreeCanvasFace badge={badge} design={design} logos={logos} pxPerMm={pxPerMm} />;
  // A logo the event has no picture for is drawn empty, as it prints; the rest use the data URLs.
  const absent = Object.entries(logos).filter(([, url]) => !url).map(([source]) => source);
  // No check-in payload (a provisional badge): print no QR rather than the designer's placeholder pattern.
  const settings = badge.checkin_payload ? design.settings : { ...design.settings, showQr: false };
  return <BadgeCanvas settings={settings} values={badgeValues(badge)} pxPerMm={pxPerMm} designId={design.design_id}
    qrValue={badge.checkin_payload} images={{ logos, absent, photo: badge.photo ?? null }} />;
}
