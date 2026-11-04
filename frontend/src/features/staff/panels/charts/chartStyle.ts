export const REPORT_CHART_COLORS = [
  "rgb(var(--chart-accent))", "rgb(var(--chart-info))", "rgb(var(--chart-success))",
  "rgb(var(--chart-warn))", "rgb(var(--chart-danger))",
];

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
