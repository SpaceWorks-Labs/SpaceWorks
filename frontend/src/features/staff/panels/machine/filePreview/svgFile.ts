import { t } from "@lingui/core/macro";
/**
 * A member's own SVG, made safe to show as an <img> (GAP2 M5). An image element never runs scripts or
 * fetches anything, and this strips what could on its own anyway: scripts, foreign content, event
 * handlers, and every reference that is not to the same document (`#id`). Refuses DTDs and entities.
 */
export const MAX_SVG_BYTES = 10 * 1024 ** 2;
const REMOVED = new Set(["script", "foreignobject", "iframe", "object", "embed", "audio", "video", "canvas", "handler"]);
const OUTSIDE = /url\(\s*['"]?(?!#)|@import|expression\(|javascript:/i;

export function sanitizeSvg(text: string) {
  if (text.length > MAX_SVG_BYTES || /<!DOCTYPE|<!ENTITY/i.test(text)) throw new Error(t`Unsafe SVG.`);
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  if (doc.querySelector("parsererror") || doc.documentElement.localName !== "svg") throw new Error(t`Invalid SVG.`);
  const nodes = Array.from(doc.querySelectorAll("*"));
  if (nodes.length > 200_000) throw new Error(t`SVG exceeds the preview limit.`);
  for (const node of nodes) {
    const name = node.localName.toLowerCase();
    if (REMOVED.has(name) || (name === "style" && OUTSIDE.test(node.textContent ?? ""))) { node.remove(); continue; }
    for (const attr of Array.from(node.attributes)) {
      const value = attr.value.replace(/\s/g, "");
      if (/^on/i.test(attr.localName)
        || (attr.localName === "href" && !value.startsWith("#"))
        || ((attr.localName === "style" || /^(?:fill|stroke|filter|mask|clip-path|marker-\w+)$/.test(attr.localName)) && OUTSIDE.test(attr.value))) {
        node.removeAttributeNode(attr);
      }
    }
  }
  return new XMLSerializer().serializeToString(doc);
}
