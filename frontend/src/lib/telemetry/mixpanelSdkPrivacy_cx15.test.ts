import { afterEach, expect, it, vi } from "vitest";
import { loadMixpanel } from "./adapters/mixpanelSdk";
import { deploymentMixpanel } from "./mixpanelConfig";

afterEach(() => {
  document.getElementById("spaceworks-mixpanel")?.remove();
  delete window.mixpanel; delete window.__MIXPANEL__;
  vi.unstubAllGlobals(); vi.restoreAllMocks();
});

it("sets anonymous CORS and no-referrer before assigning src, including before append", async () => {
  const descriptor = Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, "src")!;
  const assigned: (string | null)[][] = [];
  vi.spyOn(HTMLScriptElement.prototype, "src", "set").mockImplementation(function (this: HTMLScriptElement, value: string) {
    assigned.push([this.crossOrigin, this.referrerPolicy]);
    descriptor.set!.call(this, value);
  });
  const abort = new AbortController();
  const pending = loadMixpanel("https://sdk.example.test", abort.signal);
  expect(assigned).toEqual([["anonymous", "no-referrer"]]);
  const script = document.getElementById("spaceworks-mixpanel") as HTMLScriptElement;
  expect(script.crossOrigin).toBe("anonymous"); expect(script.referrerPolicy).toBe("no-referrer");
  abort.abort(); expect(await pending).toBeNull();
});

it.each(["https://app.example.test", "https://APP.example.test:443"])("refuses same-origin SDK mirror %s in config and loader", async sdkHost => {
  // HTTPS is required by the config grammar; jsdom's default origin may be HTTP.
  vi.stubGlobal("location", new URL("https://app.example.test/about"));
  window.__MIXPANEL__ = { token: "public-token", apiHost: "https://api.mixpanel.com", sdkHost };
  expect(deploymentMixpanel()).toBeNull();
  expect(await loadMixpanel(sdkHost, new AbortController().signal)).toBeNull();
  expect(document.getElementById("spaceworks-mixpanel")).toBeNull();
  expect(window.mixpanel).toBeUndefined();
});

it("retains a cross-origin mirror with an exact configured origin", () => {
  window.__MIXPANEL__ = { token: "public-token", apiHost: "https://api.mixpanel.com", sdkHost: "https://sdk.example.test" };
  expect(deploymentMixpanel()).toEqual(window.__MIXPANEL__);
});
