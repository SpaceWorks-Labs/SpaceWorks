import { beforeEach, describe, expect, it, vi } from "vitest";
import { TelemetryController } from "./controller";
import { deniedConsent, readConsent, saveConsent } from "./policy";

describe("telemetry admission", () => {
  beforeEach(() => { localStorage.clear(); window.history.replaceState(null, "", "/about"); });
  it("does not even import a provider without consent", async () => {
    const load = vi.fn();
    await new TelemetryController().start(new URL(location.href), deniedConsent(), [{ purpose: "analytics", load }], () => true);
    expect(load).not.toHaveBeenCalled();
  });
  it("does not initialize an import resolved after its scope is revoked", async () => {
    let resolve!: (value: { purpose: "analytics"; start: () => Promise<void>; stop: () => void }) => void;
    const load = () => new Promise<{ purpose: "analytics"; start: () => Promise<void>; stop: () => void }>(r => { resolve = r; });
    const start = vi.fn(async () => {}), controller = new TelemetryController();
    const pending = controller.start(new URL(location.href), { ...deniedConsent(), analytics: true }, [{ purpose: "analytics", load }], () => true);
    controller.stop(); resolve({ purpose: "analytics", start, stop: vi.fn() }); await pending;
    expect(start).not.toHaveBeenCalled();
  });
  it("does not reuse a different tenant or configuration consent", () => {
    expect(saveConsent("tenant-a:config-1", { ...deniedConsent(), analytics: true })).toBe(true);
    expect(readConsent("tenant-b:config-1")).toEqual(deniedConsent());
    expect(readConsent("tenant-a:config-2")).toEqual(deniedConsent());
  });
});

it("never selects platform while a tenant slug is unresolved", async () => {
  const { telemetryScope } = await import("./scope");
  expect(telemetryScope(new URL("/m/workshop", location.origin), false)).toEqual({ kind: "tenant", slug: "workshop" });
  expect(telemetryScope(new URL("/", location.origin), true)).toEqual({ kind: "none" });
});

it("does not start the legacy provider without analytics consent", async () => {
  const load = vi.fn();
  await new TelemetryController().start(new URL(location.href), deniedConsent(), [{ purpose: "analytics", load }], () => true);
  expect(load).not.toHaveBeenCalled();
});
