// Maker-file preview vendors (three, the occt WASM, the preview worker and the KiCad renderer)
// are fetched only when someone opens a preview: never precached on install, runtime-cached on
// first use. The worker policy imports this pattern; scripts/kiosk-pwa.ts and
// scripts/verify-pwa-build.mjs keep literal copies that a unit test pins to this one.
export const PREVIEW_ASSET_FILES = String.raw`three\.module-[\w-]+\.js|occt-import-js-[\w-]+\.wasm|preview\.worker-[\w-]+\.js|kicanvas-entry-[\w-]+\.js`;
export const PREVIEW_ASSET = new RegExp(`^/assets/(?:${PREVIEW_ASSET_FILES})$`);
export const PREVIEW_ASSET_COUNT = 4;
