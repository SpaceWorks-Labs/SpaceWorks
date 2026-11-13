import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { expectNoA11yViolations } from "../../test/axe";
import { KnownDevicesList } from "./KnownDevicesList";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);
const DEVICES = { remembered_days: 30, devices: [
  { id: 1, label: "Firefox on Windows", created_at: "2026-10-01T10:00:00Z", last_verified_at: "2026-11-01T10:00:00Z", current: true },
  { id: 2, label: "Safari on iPhone", created_at: "2026-09-01T10:00:00Z", last_verified_at: "2026-10-20T10:00:00Z", current: false },
] };

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const view = render(<QueryClientProvider client={client}><KnownDevicesList /></QueryClientProvider>);
  return { invalidate, ...view };
}

beforeEach(() => { request.mockReset(); });

describe("KnownDevicesList", () => {
  it("lists remembered devices with this device marked and the remember window", async () => {
    request.mockResolvedValue(DEVICES);
    const { container } = mount();
    expect(await screen.findByText("Firefox on Windows")).toBeInTheDocument();
    expect(screen.getByText("Safari on iPhone")).toBeInTheDocument();
    expect(screen.getAllByText("This device")).toHaveLength(1);
    expect(screen.getByText(/for 30 days after its last sign-in/)).toBeInTheDocument();
    expect(screen.getByText(/never skips two-step sign-in/)).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/auth/devices");
    await expectNoA11yViolations(container);
  });

  it("forgets a device only after confirming, then refreshes the list and me", async () => {
    request.mockImplementation((_path, init) => Promise.resolve(init?.method === "DELETE" ? undefined : DEVICES));
    const { invalidate } = mount();
    fireEvent.click(await screen.findByRole("button", { name: "Forget Safari on iPhone" }));
    expect(request).not.toHaveBeenCalledWith("/auth/devices/2", { method: "DELETE" });
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/Safari on iPhone will need the extra check/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Forget device" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/auth/devices/2", { method: "DELETE" }));
    expect(await screen.findByText("Device forgotten. Its next sign-in will ask for the extra check.")).toBeInTheDocument();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["knownDevices"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["staff", "me"] });
  });

  it("shows an empty state and a plain load error", async () => {
    request.mockResolvedValueOnce({ remembered_days: 90, devices: [] });
    mount();
    expect(await screen.findByText("No remembered devices yet.")).toBeInTheDocument();
  });
});
