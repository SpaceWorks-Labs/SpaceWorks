import { logoMasters } from "./spaceWorksLogoPaths";

/**
 * Decorative facets of the open box (brand p.13 "Built from the box": flap shapes as quiet accents).
 * The paths are the symbol master's own top diamond and right face, verbatim, so the 1.2-unit hairline
 * gap between them is the logo's. At most two facets render: this is never the logo, which is never
 * recoloured, rotated or animated (p.8). Callers position it absolutely inside a field whose rounded,
 * overflow-hidden corner crops it, and keep text out of the space it occupies.
 */
export type BrandFacetsProps = {
  /** Rendered width of the diamond, in px. */
  size?: "sm" | "md" | "lg" | "xl";
  /** orange-yellow: the p.13 pair. teal / orange: the diamond alone (space-card covers). */
  tone?: "orange-yellow" | "teal" | "orange";
  className?: string;
};

const WIDTHS = { sm: 128, md: 216, lg: 360, xl: 440 } as const;
const diamond = logoMasters.symbol.paths[2];
const face = logoMasters.symbol.paths[1];
const FILLS = {
  "orange-yellow": ["rgb(var(--color-emphasis))", "rgb(var(--color-warn))"],
  teal: ["rgb(var(--color-accent))"],
  orange: ["rgb(var(--color-emphasis))"],
} as const;

export function BrandFacets({ size = "md", tone = "orange-yellow", className = "" }: BrandFacetsProps) {
  const pair = tone === "orange-yellow";
  // Diamond spans x 22.7–112.4, y 16.2–79.5; the right face reaches y 125.6 (master viewBox 0 0 136 126).
  const [x, y, w, h] = pair ? [22, 16, 92, 110] : [22, 16, 92, 64];
  const width = WIDTHS[size];
  return <svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" viewBox={`${x} ${y} ${w} ${h}`}
    width={width} height={Math.round(width * h / w)} data-facets={tone}
    className={`sw-facets pointer-events-none block max-w-none select-none ${className}`}>
    <path fill={FILLS[tone][0]} d={diamond.d} />
    {pair ? <path fill={FILLS[tone][1]} d={face.d} /> : null}
  </svg>;
}
