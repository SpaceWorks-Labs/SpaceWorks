// A static, scaled drawing of one side: template gallery, version history and anywhere a
// card needs showing small. Same layer views as the canvas, no interaction.
import type { Side, Watermark } from "./cardTypes";
import { CardLayerView, useAssetUrl } from "./CardLayerView";
import { SideBackground } from "./SideBackground";
import { WatermarkView } from "./WatermarkView";

export function CardThumbnail({ side, designId, values, mono = false, width, label, watermark }: {
  side: Side; designId: number; values: Record<string, string>; mono?: boolean; width: number; label: string;
  watermark?: Watermark;
}) {
  const backgroundUrl = useAssetUrl(designId, side.background.kind === "image" ? side.background.asset_id : null);
  const px = width / side.page_width_mm;
  return <div role="img" aria-label={label}
    className="pointer-events-none relative shrink-0 select-none overflow-hidden rounded-[3.18mm] outline outline-1 outline-line"
    style={{ width, height: side.page_height_mm * px }}>
    <SideBackground side={side} mono={mono} imageUrl={backgroundUrl} px={px} />
    <WatermarkView watermark={watermark} widthMm={side.page_width_mm} heightMm={side.page_height_mm} px={px} mono={mono}
      designId={designId} />
    {side.layers.map((layer) => layer.hidden ? null : <div key={layer.id} aria-hidden="true" className="absolute"
      style={{ left: layer.x_mm * px, top: layer.y_mm * px, width: layer.w_mm * px, height: layer.h_mm * px,
        transform: `rotate(${layer.rotation}deg)`, opacity: (layer.opacity ?? 100) / 100 }}>
      <CardLayerView layer={layer} px={px} values={values} designId={designId} mono={mono} />
    </div>)}
  </div>;
}
