import { expect, it, vi } from "vitest";
import { installTelemetryBoundary } from "./boundary";

it("keeps same-tenant safe public navigation in the SPA", () => {
  history.replaceState(null, "", "/m/lab/events");
  const stop = vi.fn();
  const dispose = installTelemetryBoundary(() => true, stop, url => url.pathname.match(/^\/m\/([^/]+)/)?.[1] ?? "root");
  try { history.pushState(null, "", "/m/lab/machines"); expect(location.pathname).toBe("/m/lab/machines"); expect(stop).not.toHaveBeenCalled(); }
  finally { dispose(); }
});
