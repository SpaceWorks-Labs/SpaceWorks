import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import { GuestPassScan, isGuestPassToken } from "./GuestPassScan";
import { WalkInGuestPassResult } from "./WalkInGuestPassResult";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);

describe("guest pass desk checks", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

  it("recognises only gp1 tokens", () => {
    expect(isGuestPassToken("gp1.42.0123abcdef0123abcdef0123abcdef")).toBe(true);
    expect(isGuestPassToken("https://example.org/qr/abc")).toBe(false);
    expect(isGuestPassToken("gp1.x.abc")).toBe(false);
  });

  it("shows a valid pass and a refused one in plain words", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce({ valid: true, reason: "", pass_id: 4, holder_name: "Grace", kind: "day",
      valid_until: "2026-11-10T21:00:00Z", entitlements: { borrow: "on_site" } })
      .mockResolvedValueOnce({ valid: false, reason: "revoked", pass_id: 4, holder_name: "Grace", kind: "day", valid_until: null, entitlements: {} });
    wrap(<GuestPassScan makerspaceId={3} />);
    fireEvent.change(screen.getByLabelText(/Pass code/), { target: { value: "gp1.4.abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Check pass" }));
    expect(await screen.findByText("Valid pass")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-passes/scan", { method: "POST", body: JSON.stringify({ token: "gp1.4.abc" }) });
    fireEvent.change(screen.getByLabelText(/Pass code/), { target: { value: "gp1.4.abd" } });
    fireEvent.click(screen.getByRole("button", { name: "Check pass" }));
    expect(await screen.findByText("This pass was withdrawn.")).toBeVisible();
  });

  it("offers the desk waiver stamp after a walk-in gets a pass", async () => {
    vi.mocked(staffRequest).mockResolvedValue({});
    wrap(<WalkInGuestPassResult makerspaceId={3} result={{ user_id: 9, display_name: "Walk In", username: "walkin", is_walk_in: true,
      guest_pass_id: 77, guest_pass_valid_until: "2026-11-10T21:00:00Z", waiver_accepted: false }} />);
    expect(screen.getByText(/Walk In has a guest pass/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Waiver accepted at the desk" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-passes/77/waiver", { method: "POST", body: "{}" }));
    expect(await screen.findByText("Waiver accepted.")).toBeVisible();
  });
});
