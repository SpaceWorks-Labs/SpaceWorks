import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TelemetryConsent } from "./TelemetryConsent";
import { consentStorageKey, readConsent, saveConsent, type Consent } from "../lib/telemetry/policy";
import { TelemetryController } from "../lib/telemetry/controller";
it("applies consent withdrawal received from another tab", () => {
 const key=consentStorageKey("scope"), onChange=vi.fn(); localStorage.setItem(key,JSON.stringify({analytics:true,replay:false,diagnostics:false}));
 const view=render(<TelemetryConsent scope="scope" onChange={onChange} />);
 try { localStorage.removeItem(key); fireEvent(window,new StorageEvent("storage",{key,storageArea:localStorage,newValue:null})); expect(onChange).toHaveBeenLastCalledWith({analytics:false,replay:false,diagnostics:false}); expect((screen.getByLabelText("Usage analytics") as HTMLInputElement).checked).toBe(false); } finally { view.unmount();localStorage.removeItem(key); }
});

it("keeps a readable old grant denied after remount when storage writes and removal fail", async () => {
  const key = consentStorageKey("unwritable");
  const grant = { analytics: true, replay: true, diagnostics: true };
  localStorage.setItem(key, JSON.stringify(grant));
  const originalUrl = location.href;
  history.replaceState(null, "", "/about");
  const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("unwritable"); });
  const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("unwritable"); });
  const load = vi.fn(async () => ({ purpose: "analytics" as const, start: vi.fn(async () => {}), stop: vi.fn() }));
  const controller = new TelemetryController();
  const changed = vi.fn((consent: Consent) => { void controller.start(new URL(location.href), consent, [{ purpose: "analytics", load }], () => true); });
  try {
    expect(JSON.parse(localStorage.getItem(key)!)).toEqual(grant);
    expect(readConsent("unwritable")).toEqual({ analytics: false, replay: false, diagnostics: false });
    for (let mount = 0; mount < 2; mount++) {
      const view = render(<TelemetryConsent scope="unwritable" onChange={changed} />);
      await act(async () => {});
      expect(changed).toHaveBeenLastCalledWith({ analytics: false, replay: false, diagnostics: false });
      expect(load).not.toHaveBeenCalled();
      view.unmount();
    }
    expect(JSON.parse(localStorage.getItem(key)!)).toEqual(grant);
  } finally {
    controller.stop(); set.mockRestore(); remove.mockRestore();
    localStorage.removeItem(key); history.replaceState(null, "", originalUrl);
  }
});
it("removes the old grant when saving a withdrawal fails", () => {
 const key=consentStorageKey("failed");localStorage.setItem(key,JSON.stringify({analytics:true,replay:true,diagnostics:true}));
 const spy=vi.spyOn(Storage.prototype,"setItem").mockImplementation(() => { throw new Error("quota"); });
 try { expect(saveConsent("failed",{analytics:false,replay:false,diagnostics:false})).toBe(false);expect(readConsent("failed")).toEqual({analytics:false,replay:false,diagnostics:false}); } finally { spy.mockRestore();localStorage.removeItem(key); }
});
