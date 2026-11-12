import { boxGroundCss, boxMonoCss, boxOpenCss } from "./css";
import { boxOpenSvg } from "./markup";

/** Both themes' artwork, built once from the brand masters; CSS shows the one for `html.dark`. */
export const BOX = boxOpenSvg();

/** The animation CSS lives in a <style> added once (index.html carries the one-shot part for the splash). */
export function ensureBoxCss() {
  if (typeof document === "undefined" || document.getElementById("sw-box-css")) return;
  const style = document.createElement("style");
  style.id = "sw-box-css";
  style.textContent = `${boxOpenCss()}
${boxMonoCss()}
${boxGroundCss()}`;
  document.head.append(style);
}

/**
 * The colour behind the mark: the first opaque background up the tree. The moving flaps are outlined in it (as the
 * masters separate their parts with gaps of ground), so a sidebar or island ground shows no halo.
 */
export function boxGroundColour(start: Element | null): string | undefined {
  for (let node = start; node; node = node.parentElement) {
    const colour = getComputedStyle(node).backgroundColor;
    if (!colour || colour === "transparent") continue;
    // The last component of rgb()/rgba()/"... / a)" is the alpha only when there are four; three means opaque.
    const parts = /\(([^)]*)\)$/.exec(colour)?.[1].split(/[\s,/]+/).filter(Boolean) ?? [];
    if (parts.length < 4 || Number(parts[3]) >= 0.99) return colour;
  }
  return undefined;
}
