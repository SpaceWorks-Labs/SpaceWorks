import { expect, it, vi } from "vitest";
import { installTelemetryBoundary } from "./boundary";
it("prevents later popstate listeners when a private destination requires isolation", () => {
 history.replaceState(null,"","/about");const later=vi.fn(),stop=vi.fn(), rawReplace=history.replaceState.bind(history);const dispose=installTelemetryBoundary(() => true,stop,() => "root");window.addEventListener("popstate",later);
 try { rawReplace(null,"","/member");window.dispatchEvent(new PopStateEvent("popstate"));expect(stop).toHaveBeenCalledOnce();expect(later).not.toHaveBeenCalled(); }
 finally { dispose();window.removeEventListener("popstate",later); }
});
