import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: request }));

import { StructuredApiError } from "../../../lib/api";
import type { CardDesign } from "../../../components/card-designer/cardTypes";
import { defaultSettings } from "./badgeNormalize";
import { SAVE_DELAY_MS, useBadgeDesign } from "./useBadgeDesign";

const design = (revision = 3) => ({ id: 9, revision, can_edit: true,
  document: { version: 2, source: { format: "badge_v1", settings: defaultSettings("Build Night", "Tinkerspace") } } }) as unknown as CardDesign;
const context = { canEdit: true, eventTitle: "Build Night", organisationName: "Tinkerspace" };

function setup(row = design()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return renderHook(() => useBadgeDesign(row, context), { wrapper });
}

beforeEach(() => { vi.useFakeTimers(); request.mockReset(); window.localStorage.clear(); });
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("badge autosave", () => {
  it("saves 800 ms after a change with the badge source and the revision, then reads Saved", async () => {
    request.mockImplementation(async (_path: string, init: RequestInit) => ({ ...design(4), document: JSON.parse(String(init.body)).document }));
    const { result } = setup();
    act(() => result.current.update({ heading: "Hack Night" }));
    expect(result.current.status).toBe("pending");
    await act(async () => { await vi.advanceTimersByTimeAsync(SAVE_DELAY_MS - 1); });
    expect(request).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    const [path, init] = request.mock.calls[0];
    expect(path).toBe("/admin/card-designs/9");
    const body = JSON.parse(String(init.body));
    expect(body.revision).toBe(3);
    expect(body.document).toMatchObject({ version: 2, source: { format: "badge_v1", settings: { heading: "Hack Night" } } });
    expect(result.current.status).toBe("saved");
  });

  it("keeps the design on this device when the network drops, and saves when it comes back", async () => {
    request.mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValue(design(4));
    const { result } = setup();
    act(() => result.current.update({ heading: "Offline night" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(SAVE_DELAY_MS); });
    expect(result.current.status).toBe("local");
    expect(JSON.parse(window.localStorage.getItem("sw:card-design-draft:9") ?? "{}").document.source.settings.heading).toBe("Offline night");
    await act(async () => { window.dispatchEvent(new Event("online")); await vi.runAllTimersAsync(); });
    expect(request).toHaveBeenCalledTimes(2);
    expect(result.current.status).toBe("saved");
    expect(window.localStorage.getItem("sw:card-design-draft:9")).toBeNull();
  });

  it("does not call the server while the browser is offline", async () => {
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    const { result } = setup();
    act(() => result.current.update({ heading: "No signal" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(SAVE_DELAY_MS); });
    expect(request).not.toHaveBeenCalled();
    expect(result.current.status).toBe("local");
  });

  it("on a 409 asks whose version wins; Keep mine resaves over the newer revision", async () => {
    request.mockRejectedValueOnce(new StructuredApiError(409, { code: "card_design_conflict", detail: "Someone else saved." }))
      .mockResolvedValueOnce(design(7)).mockResolvedValueOnce(design(8));
    const { result } = setup();
    act(() => result.current.update({ heading: "Mine" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(SAVE_DELAY_MS); });
    expect(result.current.conflict).toBe(true);
    expect(result.current.status).toBe("error");
    await act(async () => { await result.current.keepMine(); });
    const resave = JSON.parse(String(request.mock.calls[2][1].body));
    expect(resave.revision).toBe(7);
    expect(resave.document.source.settings.heading).toBe("Mine");
    expect(result.current.conflict).toBe(false);
  });

  it("offers back a device copy kept for this exact revision", () => {
    const kept = { ...defaultSettings("Build Night", "Tinkerspace"), heading: "Kept here" };
    window.localStorage.setItem("sw:card-design-draft:9", JSON.stringify({ revision: 3, savedAt: "2026-11-11T10:00:00Z",
      document: { version: 2, source: { format: "badge_v1", settings: kept } } }));
    const { result } = setup();
    expect(result.current.device?.savedAt).toBe("2026-11-11T10:00:00Z");
    act(() => result.current.restoreDevice());
    expect(result.current.settings.heading).toBe("Kept here");
    expect(result.current.device).toBeNull();
  });

  it("undo and redo restore whole settings snapshots", () => {
    request.mockResolvedValue(design(4));
    const { result } = setup();
    act(() => result.current.update({ template: "bold" }));
    expect(result.current.settings.template).toBe("bold");
    act(() => result.current.undo());
    expect(result.current.settings.template).toBe("classic");
    act(() => result.current.redo());
    expect(result.current.settings.template).toBe("bold");
  });
});
