import { describe, expect, it, vi } from "vitest";
import { plausible } from "./adapters/plausible";
import { clarity } from "./adapters/clarity";

describe("provider admission", () => {
  it("does not emit a Plausible request after cancellation", async () => {
    const fetcher = vi.spyOn(window, "fetch"); const abort = new AbortController(); abort.abort();
    await plausible("example.org", "https://metrics.example", "/about").start(abort.signal, () => true);
    expect(fetcher).not.toHaveBeenCalled(); fetcher.mockRestore();
  });
  it("does not add a Clarity script after admission expires", async () => {
    const before = document.querySelectorAll('script[src*="clarity.ms"]').length;
    await clarity("project").start(new AbortController().signal, () => false);
    expect(document.querySelectorAll('script[src*="clarity.ms"]')).toHaveLength(before);
  });
});

it("uses a fixed GA4 host and disables automatic pageviews", async () => {
  const { ga4 } = await import("./adapters/ga4");
  const adapter = ga4("G-EXAMPLE", "/about");
  await adapter.start(new AbortController().signal, () => true);
  expect(document.querySelector('script[src^="https://www.googletagmanager.com/gtag/js"]')).not.toBeNull();
  expect(window.dataLayer).toContainEqual(["config", "G-EXAMPLE", expect.objectContaining({ send_page_view: false, allow_google_signals: false })]);
  adapter.stop();
});

it("disables only the owned GA4 measurement and preserves an existing opt-out", async () => {
  const { ga4 } = await import("./adapters/ga4");
  const key = "ga-disable-G-SWTEST", other = "ga-disable-G-OTHER";
  const original = Reflect.get(window, key), originalOther = Reflect.get(window, other);
  const layer = window.dataLayer, tag = window.gtag;
  try {
    Reflect.set(window, key, false); Reflect.set(window, other, false);
    const adapter = ga4("G-SWTEST", "/about");
    await adapter.start(new AbortController().signal, () => true);
    adapter.stop();
    expect(Reflect.get(window, key)).toBe(true);
    expect(Reflect.get(window, other)).toBe(false);
    const optedOut = ga4("G-SWTEST", "/about");
    await optedOut.start(new AbortController().signal, () => true);
    expect(Reflect.get(window, key)).toBe(true);
    optedOut.stop();
    expect(document.querySelector('script[src$="id=G-SWTEST"]')).toBeNull();
  } finally {
    for (const [name, value] of [[key, original], [other, originalOther]] as const) {
      if (value === undefined) Reflect.deleteProperty(window, name); else Reflect.set(window, name, value);
    }
    window.dataLayer = layer; window.gtag = tag;
  }
});
