import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest, StructuredApiError } from "../../../lib/api";
import { GuestPassDesk } from "./GuestPassDesk";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const pass = {
  id: 11, kind: "sponsored", status: "active", valid_from: "2026-11-10T09:00:00Z", valid_until: "2026-11-10T21:00:00Z",
  holder_id: 5, holder_name: "Grace Guest", holder_email: "grace@example.org", sponsor_id: 2, sponsor_name: "Ada",
  product_id: null, entitlements: { borrow: "on_site", machines: "none" }, waiver_version: null, waiver_accepted_at: null,
  payment_status: null, revoked_at: null, revoked_reason: "", converted_membership_id: null, created_at: "2026-11-10T08:00:00Z",
};

function show(dayPassesOn = true) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <GuestPassDesk makerspaceId={3} dayPassesOn={dayPassesOn} />
  </QueryClientProvider>);
}

describe("GuestPassDesk", () => {
  beforeEach(() => {
    vi.mocked(staffRequest).mockReset();
    vi.mocked(staffRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.includes("/guest-passes?")) return { count: 1, next: null, previous: null, results: [pass] };
      if (path.endsWith("/day-pass-products")) return [{ id: 4, name: "Day pass", amount: "10.00", currency: "EUR", entitlements: {}, daily_cap: null, is_public: true, is_active: true, archived_at: null }];
      if (path.endsWith("/sell")) return { pass_id: 12, status: "issued", payment_id: 9, payment_status: "pending", amount: "10.00", currency: "EUR" };
      if (options?.method === "POST") return { ...pass, waiver_accepted_at: "2026-11-10T10:00:00Z" };
      return {};
    });
  });

  it("lists passes with what they allow and stamps the desk waiver", async () => {
    show();
    expect(await screen.findByText("Grace Guest")).toBeVisible();
    expect(screen.getByText(/Guest of Ada/)).toBeVisible();
    expect(screen.getByText(/On site only/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Waiver accepted at the desk" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-passes/11/waiver", { method: "POST", body: "{}" }));
  });

  it("filters the roster by status and kind", async () => {
    show();
    await screen.findByText("Grace Guest");
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "day" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(expect.stringContaining("kind=day")));
  });

  it("withdraws a pass with a reason", async () => {
    show();
    await screen.findByText("Grace Guest");
    fireEvent.click(screen.getByRole("button", { name: "Withdraw pass" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Decision reason"), { target: { value: "Left early" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm decision" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-passes/11/revoke", { method: "POST", body: JSON.stringify({ reason: "Left early" }) }));
  });

  it("issues a pass by e-mail and sells a day pass with the amount owed", async () => {
    show();
    await screen.findByText("Grace Guest");
    fireEvent.click(screen.getByRole("button", { name: "Sell a day pass" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Guest's e-mail or account number/), { target: { value: "new@example.org" } });
    await within(dialog).findByRole("option", { name: /Day pass/ });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record sale" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-passes/sell", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(vi.mocked(staffRequest).mock.calls.find(([path]) => String(path).endsWith("/sell"))![1]!.body as string);
    expect(body).toMatchObject({ holder_email: "new@example.org", product_id: 4 });
    expect(body.operation_id).toBeTruthy();
    expect(await screen.findByText(/is owed/)).toBeVisible();
  });

  it("hides the sale without day passes and shows plain copy for a refusal", async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string) => {
      if (path.includes("/guest-passes?")) return { count: 0, next: null, previous: null, results: [] };
      throw new StructuredApiError(409, { code: "visit_cap_reached", detail: "raw" });
    });
    show(false);
    expect(await screen.findByText(/No guest passes yet/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Sell a day pass" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Issue a pass" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Guest's e-mail or account number/), { target: { value: "7" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Issue pass" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("visit limit");
  });
});
