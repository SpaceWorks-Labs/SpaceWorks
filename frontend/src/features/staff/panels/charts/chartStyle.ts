/** The five bright brand colours (decision 380), identical in light and dark. Contrast is the edge's job. */
export const REPORT_CHART_COLORS = [1, 2, 3, 4, 5].map((n) => `rgb(var(--chart-${n}))`);
/** Reserved for a value that is semantically bad or negative; never a series colour. */
export const chartDanger = "rgb(var(--chart-danger))";
/** 1px edge on every filled mark and the casing under every line, so a bright fill never carries the boundary. */
export const edge = "rgb(var(--chart-edge))";
/** Bars and segments are divs: an inset 1px edge keeps the box size and the fill intact. */
export const markStyle = (identity: string) => ({ backgroundColor: seriesColor(identity), boxShadow: `inset 0 0 0 1px ${edge}` });

/** Identity-based colour survives sorting, filtering and adding another series. */
export function seriesIndex(identity: string) {
  let hash = 0;
  for (const character of identity) hash = (Math.imul(hash, 31) + character.charCodeAt(0)) >>> 0;
  return hash;
}
export const seriesColor = (identity: string) => REPORT_CHART_COLORS[seriesIndex(identity) % REPORT_CHART_COLORS.length];
export const seriesDash = (identity: string) => ["", "8 4", "2 4", "10 3 2 3"][seriesIndex(identity) % 4];
export const ink = "rgb(var(--color-ink))";
export const panel = "rgb(var(--color-panel))";
export const focusClass = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
