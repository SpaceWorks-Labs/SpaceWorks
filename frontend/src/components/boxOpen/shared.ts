import { boxMonoCss, boxOpenCss } from "./css";
import { boxOpenSvg } from "./markup";

/** Both themes' artwork, built once from the brand masters; CSS shows the one for `html.dark`. */
export const BOX = boxOpenSvg();

/** The animation CSS lives in a <style> added once (index.html carries the one-shot part for the splash). */
export function ensureBoxCss() {
  if (typeof document === "undefined" || document.getElementById("sw-box-css")) return;
  const style = document.createElement("style");
  style.id = "sw-box-css";
  style.textContent = `${boxOpenCss()}
${boxMonoCss()}`;
  document.head.append(style);
}
