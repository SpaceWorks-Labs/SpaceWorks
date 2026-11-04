// Card fonts for the canvas, loaded from THIS app (never from Google): the bytes come
// through the authenticated design route and are registered with the FontFace API.
import { staffRequestBlob } from "../../lib/api";

const loaded = new Map<string, Promise<boolean>>();

export function cssFamily(family: string) {
  return `"SW Card ${family}"`;
}

export function fontSlug(family: string) {
  return family.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export function loadCardFont(designId: number, family: string, weight: number) {
  const key = `${family}:${weight}`;
  if (typeof FontFace === "undefined" || typeof document === "undefined") return Promise.resolve(false);
  if (!loaded.has(key)) {
    loaded.set(key, staffRequestBlob(`/admin/card-designs/${designId}/fonts/${fontSlug(family)}/${weight}`)
      .then((blob) => blob.arrayBuffer())
      .then(async (buffer) => {
        const face = new FontFace(`SW Card ${family}`, buffer, { weight: String(weight) });
        await face.load();
        document.fonts.add(face);
        return true;
      })
      .catch(() => {
        loaded.delete(key);
        return false;
      }));
  }
  return loaded.get(key)!;
}
