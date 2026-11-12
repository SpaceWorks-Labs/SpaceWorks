// A side's background as layers: colour or gradient, then an image (fit, zoom, focal point, blur, darken),
// then the overlay gradient (per-stop alpha). Order is the server's: image, blur, dim, overlay.
import type { Side } from "./cardTypes";
import { cssNumber, gradientCss, imageFrameStyle, rgbaCss, rgbCss } from "./studioMath";

export function SideBackground({ side, mono, imageUrl, px }: { side: Side; mono: boolean; imageUrl: string | null; px: number }) {
  const { background, overlay } = side;
  const w = side.page_width_mm, h = side.page_height_mm;
  if (mono) return <div aria-hidden="true" className="absolute inset-0" style={{ background: "#FFFFFF" }} />;
  return <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
    {background.kind === "colour" ? <div className="absolute inset-0" style={{ background: rgbCss(background.colour) }} /> : null}
    {background.kind === "gradient" ? <div className="absolute inset-0" style={{ background: gradientCss(background, w, h) }} /> : null}
    {background.kind === "image" ? <>
      <div className="absolute inset-0" style={{ background: rgbCss(background.fallback ?? "#FFFFFF") }} />
      {imageUrl ? <img src={imageUrl} alt="" className="absolute inset-0"
        style={{ ...imageFrameStyle(background.fit, background.zoom, background.focal_x_pct, background.focal_y_pct),
          filter: background.blur_mm ? `blur(${cssNumber(background.blur_mm, 0, 0, 50) * px}px)` : undefined }} /> : null}
      {background.dim_pct > 0 ? <div className="absolute inset-0" style={{ background: rgbaCss("#000000", background.dim_pct) }} /> : null}
    </> : null}
    {overlay ? <div className="absolute inset-0" style={{ background: gradientCss(overlay, w, h, true) }} /> : null}
  </div>;
}
