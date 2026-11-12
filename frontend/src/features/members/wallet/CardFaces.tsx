// The printed-card view (SPEC §8): the published design drawn in the browser from the design
// document, as SVG, with the same layer maths as the designer (CardLayerView). The server PDF
// stays the source of truth for printing; this is what the holder sees in My cards.
import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { CardDocument, SideName } from "../../../components/card-designer/cardTypes";
import { CardLayerView, type LiveImages } from "../../../components/card-designer/CardLayerView";
import { SideBackground } from "../../../components/card-designer/SideBackground";
import { merge } from "../../../components/card-designer/dataFields";
import { WatermarkView } from "../../../components/card-designer/WatermarkView";
import { loadCardFontWith } from "../../../components/card-designer/fontLoader";
import { memberRequest, memberRequestBlob } from "../../../lib/api";
import { cardPath, type MyCard } from "./api";

export type CardFace = LiveImages & { document: CardDocument; values: Record<string, string> };

/** Pixels per millimetre inside the SVG; the SVG itself scales to its box. */
const PX = 8;

export function useCardFace(card: MyCard, enabled: boolean) {
  return useQuery({ queryKey: ["member", "card-face", card.kind, card.id], enabled, staleTime: 5 * 60_000, retry: false,
    queryFn: () => memberRequest<CardFace>(`${cardPath(card)}/face`) });
}

export function useCardFaceFonts(card: MyCard, face: CardFace | undefined) {
  const fonts = useMemo(() => face ? [...new Set([...face.document.front.layers, ...face.document.back.layers]
    .filter((layer) => layer.font_family).map((layer) => `${layer.font_family}|${layer.font_weight ?? 400}`))] : [], [face]);
  useEffect(() => {
    fonts.forEach((key) => {
      const [family, weight] = key.split("|");
      void loadCardFontWith(family, Number(weight), (slug) => memberRequestBlob(`${cardPath(card)}/fonts/${slug}/${weight}`));
    });
  }, [card, fonts]);
}

/** What a screen reader hears for one face: the card's readable text in layer order, then its codes. */
export function describeFace(face: CardFace, side: SideName) {
  const layers = face.document[side].layers.filter((layer) => !layer.hidden);
  const text = layers.filter((layer) => layer.kind === "text" || layer.kind === "data_field")
    .map((layer) => merge(layer.text ?? "", face.values).replace(/\s+/g, " ").trim()).filter(Boolean);
  const codes = layers.flatMap((layer) => layer.kind === "desk_qr" ? ["a desk QR code"] : layer.kind === "verify_qr"
    ? ["a QR code that opens the public check page"] : layer.kind === "barcode" ? ["a barcode"] : []);
  const photo = layers.some((layer) => layer.kind === "photo") ? (face.photo ? "Your photo." : "Your initials in place of a photo.") : "";
  return [text.join(". "), photo, codes.length ? `It carries ${codes.join(" and ")}.` : ""].filter(Boolean).join(" ");
}

export function faceAspect(face: CardFace | undefined) {
  const page = face?.document.front;
  return page ? `${page.page_width_mm} / ${page.page_height_mm}` : "85.6 / 53.98";
}

export function CardFaceSvg({ face, side, label }: { face: CardFace; side: SideName; label?: string }) {
  const page = face.document[side];
  const width = page.page_width_mm * PX, height = page.page_height_mm * PX;
  const mono = face.document.mono;
  const background = page.background;
  const backgroundUrl = background.kind === "image" ? face.assets[background.asset_id] ?? null : null;
  const watermark = face.document.watermark;
  return <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" role={label ? "img" : undefined}
    aria-label={label} aria-hidden={label ? undefined : true}>
    <foreignObject x="0" y="0" width={width} height={height}>
      <div className="relative h-full w-full overflow-hidden">
        <SideBackground side={page} mono={mono} imageUrl={backgroundUrl} px={PX} />
        <WatermarkView watermark={watermark} widthMm={page.page_width_mm} heightMm={page.page_height_mm} px={PX} mono={mono}
          designId={0} imageUrl={watermark?.kind === "image" && watermark.asset_id ? face.assets[watermark.asset_id] ?? null : null} />
        {page.layers.map((layer) => layer.hidden ? null : <div key={layer.id} className="absolute"
          style={{ left: layer.x_mm * PX, top: layer.y_mm * PX, width: layer.w_mm * PX, height: layer.h_mm * PX,
            transform: `rotate(${layer.rotation}deg)`, opacity: (layer.opacity ?? 100) / 100 }}>
          <CardLayerView layer={layer} px={PX} values={face.values} designId={0} mono={mono} live={face} />
        </div>)}
      </div>
    </foreignObject>
  </svg>;
}
