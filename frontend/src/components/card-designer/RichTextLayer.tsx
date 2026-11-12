// A text layer drawn from the studio layout plan as SVG: exact baselines, per-span style, one highlight
// bar and underline per line, glyph stroke and shadow. Used when a layer carries any rich property;
// plain text keeps the lighter HTML path in CardLayerView. The plan is in points; the SVG is in millimetres.
import { useMemo } from "react";

import { PT_TO_MM } from "./cardGeometry";
import type { Layer } from "./cardTypes";
import { canonicalFamily } from "./fontLoader";
import { canvasMeasure, useFontEpoch } from "./studioMeasure";
import { rgbaCss } from "./studioMath";
import { planLayer, textStroke, type MeasureText } from "./studioText";

const mm = (points: number) => points * PT_TO_MM;

export function RichTextLayer({ layer, px, values, mono, locale, measure = canvasMeasure }: {
  layer: Layer; px: number; values: Record<string, string>; mono: boolean; locale?: string; measure?: MeasureText;
}) {
  const epoch = useFontEpoch();
  const { spans, plan } = useMemo(() => planLayer(layer, values, measure, locale),
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `epoch` re-measures once fonts have loaded
  [layer, values, locale, measure, epoch]);
  const stroke = textStroke(layer);
  const shadow = layer.shadow;
  const ink = (colour: string) => (mono ? "#000000" : colour);
  const filter = shadow && shadow.opacity_pct > 0
    ? `drop-shadow(${shadow.dx_mm}px ${shadow.dy_mm}px ${Math.min(2, shadow.blur_mm) / 2}px ${rgbaCss(shadow.colour, shadow.opacity_pct)})` : undefined;
  return <svg width={layer.w_mm * px} height={layer.h_mm * px} viewBox={`0 0 ${layer.w_mm} ${layer.h_mm}`}
    style={{ overflow: "visible", display: "block" }} role="img" aria-label={plan.lines.map((line) => line.parts.map((part) => part.text).join("")).join(" ")}>
    {plan.bars.map((bar, index) => <rect key={`h${index}`} x={mm(bar.x)} y={mm(bar.y)} width={mm(bar.w)} height={mm(bar.h)}
      rx={Math.min(mm(bar.radius), mm(bar.h) / 2)} fill={mono ? "#DDDDDD" : layer.highlight?.colour} />)}
    {plan.rules.map((rule, index) => <rect key={`u${index}`} x={mm(rule.x)} y={mm(rule.y) - mm(rule.thickness) / 2} width={mm(rule.w)}
      height={mm(rule.thickness)} fill={ink(layer.underline?.colour ?? "#000000")} />)}
    <g style={{ filter }}>
      {plan.lines.map((line, index) => <text key={index} y={mm(line.baseline)} style={{ whiteSpace: "pre" }}>
        {line.parts.map((part, at) => {
          const span = spans[part.span];
          return <tspan key={at} x={mm(part.x)} fill={ink(span.colour)}
            fontFamily={`"SW Card ${canonicalFamily(span.family)}", ${canonicalFamily(span.family)}, sans-serif`}
            fontWeight={span.weight} fontSize={mm(span.size * plan.scale)} letterSpacing={mm(span.tracking)}
            stroke={stroke ? ink(stroke.colour) : undefined} strokeWidth={stroke ? mm(stroke.width_pt * 2) : undefined}
            strokeLinejoin="round" paintOrder={stroke ? "stroke" : undefined}>{part.text}</tspan>;
        })}
      </text>)}
    </g>
  </svg>;
}
