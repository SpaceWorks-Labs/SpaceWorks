import { boxOpenSvg as v200Svg } from "./v200Markup";

/** Coloured flaps keep their own colours, with no decorative bursts.
 * Reversed SVG is the exact v2.0.0 output, including its no-hole cap and paint order.
 */
export function boxOpenSvg(): string {
  const legacy = v200Svg();
  const light = legacy.split("</svg>")[0];
  const coloured = light.replace('class="lt"', 'class="colour"').replace(/;--alt:[^";]+/g, "")
    .replace(/<g class="x">[\s\S]*?<\/g>/, "");
  return `${legacy}${coloured}</svg>`;
}
