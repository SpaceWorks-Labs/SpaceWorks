export function kioskNavigation(path: string) {
  return /^\/kiosk\/[^/]+\/?$/.test(path) || /^\/m\/[^/]+\/kiosk\/[^/]+\/?$/.test(path);
}

// Maker-file preview vendors (three, the occt WASM and the preview worker, ~8 MB) are
// fetched only when someone opens a 3D/CAD preview: never precached on install,
// runtime-cached on first use instead.
export const PREVIEW_ASSET = /^\/assets\/(?:three\.module-[\w-]+\.js|occt-import-js-[\w-]+\.wasm|preview\.worker-[\w-]+\.js)$/;

export function cachePolicy(request: Pick<Request, "url" | "method" | "mode" | "headers">,
  origin: string, precachePaths: Set<string>) {
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== origin || url.pathname.startsWith("/api/")
      || request.headers.has("Authorization")) return "network";
  if (request.mode === "navigate") return kioskNavigation(url.pathname) ? "kiosk" : "network";
  if (!url.search && PREVIEW_ASSET.test(url.pathname)) return "preview";
  // Only build-manifest URLs qualify, never runtime images/evidence or config.
  return !url.search && precachePaths.has(url.pathname) ? "static" : "network";
}
