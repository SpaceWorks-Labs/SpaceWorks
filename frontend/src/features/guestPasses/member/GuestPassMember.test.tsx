import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { memberRequest, StructuredApiError } from "../../../lib/api";
import { BringAGuest } from "./BringAGuest";
import { DayPassShop } from "./DayPassShop";
import { MyGuestPasses } from "./MyGuestPasses";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn() }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
const livePass = { id: 21, kind: "day", status: "active", valid_from: "2026-11-10T09:00:00Z", valid_until: "2026-11-10T21:00:00Z",
  entitlements: { borrow: "none", machines: "supervised" }, sponsor_name: "", waiver_accepted: false, waiver_required: true,
  payment_status: "pending", wallet_platforms: ["apple", "google"] };

describe("MyGuestPasses", () => {
  const assign = vi.fn();
  beforeEach(() => {
    vi.mocked(memberRequest).mockReset();
    vi.stubGlobal("location", { ...window.location, assign });
    vi.mocked(memberRequest).mockImplementation(async (path: string) => {
      if (path.endsWith("/guest-passes")) return { passes: [livePass], visits_30d: 4, join_threshold: 3, should_prompt_join: true };
      if (path.includes("/wallet/")) return { platform: "apple", url: "https://example.org/p.pkpass", expires_in: 60 };
      if (path.endsWith("/waiver")) return { has_waiver: true, version: "v2", body: "Wear goggles." };
      return { ...livePass, waiver_accepted: true };
    });
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("shows the pass, payment step, waiver, wallet and join prompt", async () => {
    wrap(<MyGuestPasses makerspaceId={3} paymentsHref="/member/payments" joinSlot={(id) => <p>join from {id}</p>} />);
    expect(await screen.findByRole("heading", { name: "My passes" })).toBeVisible();
    expect(screen.getByText(/goes live once it is paid/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Payments" })).toHaveAttribute("href", "/member/payments");
    expect(screen.getByText("join from 21")).toBeVisible();
    expect(await screen.findByText("Wear goggles.")).toBeVisible();
    expect(screen.getByRole("region", { name: "Waiver, version v2" })).toBeVisible();
    expect(screen.queryByText(/Ask staff at the desk/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Accept waiver" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/guest-passes/21/accept-waiver", { method: "POST", body: JSON.stringify({ accepted: true }) }));
    fireEvent.click(screen.getByRole("button", { name: "Add to Apple Wallet" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://example.org/p.pkpass"));
  });

  it("points to the desk only when the waiver text cannot be read", async () => {
    vi.mocked(memberRequest).mockImplementation(async (path: string) => {
      if (path.endsWith("/guest-passes")) return { passes: [{ ...livePass, payment_status: null }], visits_30d: 1, join_threshold: 3, should_prompt_join: false };
      if (path.endsWith("/waiver")) throw new StructuredApiError(403, { code: "permission_denied" });
      return {};
    });
    wrap(<MyGuestPasses makerspaceId={3} paymentsHref="/p" />);
    expect(await screen.findByText(/Ask staff at the desk/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Accept waiver" })).toBeEnabled();
  });

  it("renders nothing when the feature is off", async () => {
    vi.mocked(memberRequest).mockRejectedValue(new StructuredApiError(404, { code: "feature_disabled" }));
    const { container } = wrap(<MyGuestPasses makerspaceId={3} paymentsHref="/p" />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});

describe("BringAGuest", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); });

  it("sends the invitation with an operation id and lists guests", async () => {
    vi.mocked(memberRequest).mockImplementation(async (_path: string, options?: RequestInit) => options?.method === "POST"
      ? { detail: "If they have an account, your guest has a pass." }
      : [{ id: 8, guest_name: "Grace", pass_date: "2026-11-10", status: "active", items_outstanding: true }]);
    wrap(<BringAGuest makerspaceId={3} />);
    expect(await screen.findByText("Grace")).toBeVisible();
    expect(screen.getByText("Items still out")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Guest's e-mail"), { target: { value: "friend@example.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Bring guest" }));
    expect(await screen.findByText(/your guest has a pass/)).toBeVisible();
    const body = JSON.parse(vi.mocked(memberRequest).mock.calls.find(([, options]) => options?.method === "POST")![1]!.body as string);
    expect(body.email).toBe("friend@example.org");
    expect(body.operation_id).toBeTruthy();
  });

  it("names the member's own refusal in plain words", async () => {
    vi.mocked(memberRequest).mockImplementation(async (_path: string, options?: RequestInit) => {
      if (options?.method === "POST") throw new StructuredApiError(403, { code: "sponsor_presence_required", detail: "raw" });
      return [];
    });
    wrap(<BringAGuest makerspaceId={3} />);
    fireEvent.change(await screen.findByLabelText("Guest's e-mail"), { target: { value: "x@example.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Bring guest" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Check in at the space first");
  });
});

describe("DayPassShop", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); });

  it("buys a priced pass and points to Payments", async () => {
    vi.mocked(memberRequest).mockImplementation(async (_path: string, options?: RequestInit) => options?.method === "POST"
      ? { pass_id: 30, status: "issued", payment_id: 9, payment_status: "pending", amount: "15.00", currency: "EUR" }
      : [{ id: 2, name: "Day pass", amount: "15.00", currency: "EUR" }]);
    wrap(<DayPassShop makerspaceId={3} paymentsHref="/m/x/member/payments" />);
    fireEvent.click(await screen.findByRole("button", { name: "Buy Day pass" }));
    expect(await screen.findByText(/is due before it goes live/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Payments" })).toHaveAttribute("href", "/m/x/member/payments");
    expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/day-passes/2/purchase", expect.objectContaining({ method: "POST" }));
  });

  it("is absent when nothing is on sale", async () => {
    vi.mocked(memberRequest).mockResolvedValue([]);
    const { container } = wrap(<DayPassShop makerspaceId={3} paymentsHref="/p" />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
