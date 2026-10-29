/**
 * The one module the app imports to draw KiCad files. Rollup emits it as
 * `/assets/kicanvas-entry-<hash>.js`, which stays out of the install precache
 * (`src/sw/previewAssets.ts`) and is runtime-cached on first use.
 *
 * KiCanvas (MIT, github.com/theacodes/kicanvas) is vendored next to this file at a pinned commit
 * with the three local patches listed in VENDORED.md. Until that source is present this entry
 * reports the renderer as unavailable and the preview degrades to the download card.
 */
export type BoardLayer = "top_copper" | "bottom_copper" | "silkscreen" | "edge_cuts";

export interface KicadViewer {
  fit(): void;
  zoom(step: 1 | -1, options: { animate: boolean }): void;
  setLayerVisible(layer: BoardLayer, visible: boolean): void;
  dispose(): void;
}

export interface KicadMountOptions {
  /** Checked source text, set through `textContent` on a `<kicanvas-source>`, never as markup. */
  text: string;
  variant: "pcb" | "sch";
  /** Drawing theme picked from the app theme; the drawing keeps KiCad's own colours. */
  theme: "light" | "dark";
}

export class KicanvasUnavailable extends Error {
  constructor() {
    super("The KiCad renderer is not installed in this build.");
    this.name = "KicanvasUnavailable";
  }
}

export async function mountKicad(_host: HTMLElement, _options: KicadMountOptions): Promise<KicadViewer> {
  throw new KicanvasUnavailable();
}
