// The printed-card view (SPEC §8): the published design drawn in the browser from the design
// document, as SVG, with the same layer maths as the designer (CardLayerView). The server PDF
// stays the source of truth for printing; this is what the holder sees in My cards.
import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { CardDocument, SideName } from "../../../components/card-designer/cardTypes";
import { backgroundStyle, CardLayerView, type LiveImages } from "../../../components/card-designer/CardLayerView";
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

export function CardFaceSvg({ face, side, label }: { face: CardFace; side: SideName; label?: string }) {
  const page = face.document[side];
  const width = page.page_width_mm * PX, height = page.page_height_mm * PX;
  const mono = face.document.mono;
  const background = mono ? { kind: "colour" as const, colour: "#FFFFFF" } : page.background;
  const backgroundUrl = background.kind === "image" ? face.assets[background.asset_id] ?? null : null;
  const watermark = face.document.watermark;
  return <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" role={label ? "img" : undefined}
    aria-label={label} aria-hidden={label ? undefined : true}>
    <foreignObject x="0" y="0" width={width} height={height}>
      <div className="relative h-full w-full overflow-hidden" style={backgroundStyle(background, backgroundUrl)}>
        {watermark?.kind === "text" && watermark.text ? <div aria-hidden="true" className="absolute inset-0 grid place-items-center font-bold"
          style={{ opacity: watermark.opacity_pct / 100, transform: `rotate(${watermark.angle_deg}deg)`, color: watermark.colour,
            fontSize: height / 6 }}>{watermark.text}</div> : null}
        {page.layers.map((layer) => layer.hidden ? null : <div key={layer.id} className="absolute"
          style={{ left: layer.x_mm * PX, top: layer.y_mm * PX, width: layer.w_mm * PX, height: layer.h_mm * PX,
            transform: `rotate(${layer.rotation}deg)`, opacity: (layer.opacity ?? 100) / 100 }}>
          <CardLayerView layer={layer} px={PX} values={face.values} designId={0} mono={mono} live={face} />
        </div>)}
      </div>
    </foreignObject>
  </svg>;
}
