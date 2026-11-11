import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { expectNoA11yViolations } from "../../test/axe";
import type { OwnBorrowing } from "./borrowingHistoryApi";
import { MemberBorrowingHistoryPage } from "./MemberBorrowingHistoryPage";

const state = vi.hoisted(() => ({ request: vi.fn(), actor: 1, enabled: true, mode: "central", publicInventory: true, extraFeatures: [] as string[] }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest: state.request, getAccessToken: () => `head.${btoa(JSON.stringify({ user_id: state.actor }))}.sig` }));
vi.mock("../../lib/tenant", () => ({
  useTenant: () => ({ mode: state.mode, slug: "lab", bootstrap: { makerspace: { id: 7, name: "Lab", public_inventory_enabled: state.publicInventory }, branding: {}, modules: ["request_workflow", "public_inventory"], features: [...(state.enabled ? ["loans.enabled"] : []), ...state.extraFeatures] } }),
  useTenantPath: () => (part = "") => `${state.mode === "single" ? "" : "/m/lab"}/${part}`,
}));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: {
  makerspace: { id: 7, name: "Lab", public_inventory_enabled: state.publicInventory }, branding: {}, modules: ["request_workflow", "public_inventory"], features: [...(state.enabled ? ["loans.enabled"] : []), ...state.extraFeatures],
}, isLoading: false }) }));
vi.mock("./MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in to your own history</p> }));

const row = (name = "Owned drill"): OwnBorrowing => ({ id: 4, status: "returned", source: "admin_direct",
  created_at: "2026-11-01T10:00:00Z", issued_at: "2026-11-02T10:00:00Z", return_due_at: "2026-11-05T10:00:00Z",
  closed_at: "2026-11-04T10:00:00Z", checked_out_at: "2026-11-02T10:00:00Z", returned_at: "2026-11-04T10:00:00Z",
  returns: [{ returned_at: "2026-11-04T10:00:00Z" }], items: [{ product_name: name, requested_quantity: 2,
    accepted_quantity: 2, issued_quantity: 2, returned_quantity: 2, damaged_quantity: 0, missing_quantity: 0, needs_fix_quantity: 0 }] });

let read: (path: string) => Promise<unknown>;
function show(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const tree = () => <QueryClientProvider client={client}><MemoryRouter initialEntries={[state.mode === "single" ? "/member/loans/history" : "/m/lab/member/loans/history"]}><Routes>
    <Route path="/m/:slug/member/loans/history" element={<MemberBorrowingHistoryPage />} />
    <Route path="/member/loans/history" element={<MemberBorrowingHistoryPage />} />
  </Routes></MemoryRouter></QueryClientProvider>;
  const view = render(tree());
  return { ...view, refresh: () => view.rerender(tree()) };
}
beforeEach(() => {
  state.actor = 1; state.enabled = true; state.mode = "central"; state.publicInventory = true; state.extraFeatures = []; state.request.mockReset();
  read = () => Promise.resolve({ count: 1, next: null, previous: null, results: [row()] });
  state.request.mockImplementation((path: string) => path === "/auth/me" ? Promise.resolve({ id: state.actor }) : read(path));
});

describe("account-only borrowing history", () => {
  it("shows own workflow dates, state and outcomes without membership, rail or private fields", async () => {
    read = () => Promise.resolve({ count: 1, next: null, previous: null, results: [{ ...row(), qr_code: "SECRET-QR", issue_remark: "PRIVATE-REMARK", storage_location: "PRIVATE-SHELF" }] });
    const { container } = show();
    expect(await screen.findByText("Owned drill")).toBeVisible();
    expect(screen.getByText("Staff handout")).toBeVisible();
    expect(screen.getByText("Return recorded")).toBeVisible();
    expect(screen.getByText("Issued 2")).toBeVisible();
    expect(state.request).toHaveBeenCalledWith("/member/makerspaces/7/borrowing-history?period=all&page=1");
    expect(container.textContent).not.toMatch(/SECRET-QR|PRIVATE-REMARK|PRIVATE-SHELF/);
    expect(screen.getByRole("link", { name: "Payments & receipts" })).toHaveAttribute("href", "/m/lab/member/payments");
    await expectNoA11yViolations(container);
  });

  it("paginates beyond a first page and resets pagination when the history view changes", async () => {
    read = path => Promise.resolve({ count: 25, next: null, previous: null, results: [row(path.includes("page=2") ? "Older drill" : "Recent drill")] });
    show();
    await screen.findByText("Recent drill");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Older drill")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Borrowing view"), { target: { value: "history" } });
    await waitFor(() => expect(state.request).toHaveBeenCalledWith("/member/makerspaces/7/borrowing-history?period=history&page=1"));
  });

  it("shows an empty history instead of inventing records", async () => {
    read = () => Promise.resolve({ count: 0, next: null, previous: null, results: [] });
    show();
    expect(await screen.findByText(/No borrowing records match this view/)).toBeVisible();
  });

  it("exposes API failures and a focused retry", async () => {
    read = () => Promise.reject(new Error("History temporarily unavailable"));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("History temporarily unavailable");
    read = () => Promise.resolve({ count: 1, next: null, previous: null, results: [row()] });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Owned drill")).toBeVisible();
  });

  it("asks a signed-out account to sign in before showing history", async () => {
    state.request.mockRejectedValue(new StructuredApiError(401, { detail: "Sign in." }));
    show();
    expect(await screen.findByText("Sign in to your own history")).toBeVisible();
    expect(screen.queryByText("Owned drill")).toBeNull();
  });

  it("never requests history or inventory when lending is unavailable", async () => {
    state.enabled = false;
    show();
    expect(await screen.findByText("Borrowing history is unavailable for this space.")).toBeVisible();
    expect(state.request).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/m/lab/");
  });

  it("does not carry another account's cached history across an account switch", async () => {
    read = () => Promise.resolve({ count: 1, next: null, previous: null, results: [row(state.actor === 1 ? "First owner drill" : "Second owner drill")] });
    const view = show();
    expect(await screen.findByText("First owner drill")).toBeVisible();
    state.actor = 2;
    view.refresh();
    expect(await screen.findByText("Second owner drill")).toBeVisible();
    expect(screen.queryByText("First owner drill")).toBeNull();
  });

  it("shows a loading state while the owned history read is pending", async () => {
    let complete!: (body: unknown) => void;
    read = () => new Promise(resolve => { complete = resolve; });
    show();
    await waitFor(() => expect(state.request).toHaveBeenCalledWith("/member/makerspaces/7/borrowing-history?period=all&page=1"));
    expect(screen.getByRole("status", { name: "Loading content" })).toBeVisible();
    await act(async () => complete({ count: 1, next: null, previous: null, results: [row()] }));
    expect(await screen.findByText("Owned drill")).toBeVisible();
  });

  it("preserves an explicit account refusal instead of treating it as an empty successful history", async () => {
    read = () => Promise.reject(new StructuredApiError(403, { detail: "An active, unrestricted account is required." }));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("An active, unrestricted account is required.");
    expect(screen.queryByText("Owned drill")).toBeNull();
  });

  it("keeps the single-tenant inventory, money and account links in the single-tenant route family", async () => {
    state.mode = "single";
    show();
    await screen.findByText("Owned drill");
    expect(screen.getByRole("link", { name: "Browse inventory" })).toHaveAttribute("href", "/inventory");
    expect(screen.getByRole("link", { name: "Payments & receipts" })).toHaveAttribute("href", "/member/payments");
    expect(screen.getByRole("link", { name: "Your account" })).toHaveAttribute("href", "/member/account");
  });

  it("links the actual borrowing guide only while the space's Help centre is enabled", async () => {
    state.extraFeatures = ["platform.help_centre"];
    const view = show();
    await screen.findByText("Owned drill");
    expect(screen.getByRole("link", { name: "Help for this page (opens in a new tab)" })).toHaveAttribute("href", "/m/lab/help/member/borrow-tools");
    state.extraFeatures = [];
    view.refresh();
    expect(screen.queryByRole("link", { name: "Help for this page (opens in a new tab)" })).toBeNull();
  });

  it("keeps private own history available when public Inventory is unpublished without linking to its unavailable page", async () => {
    state.publicInventory = false;
    show();
    expect(await screen.findByText("Owned drill")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Browse inventory" })).toBeNull();
    expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/m/lab/");
    expect(state.request).toHaveBeenCalledWith("/member/makerspaces/7/borrowing-history?period=all&page=1");
  });

  it("lets an account-only borrower withdraw a request that has not been handed over yet (loans.withdrawals)", async () => {
    state.extraFeatures = ["loans.withdrawals"];
    read = () => Promise.resolve({ count: 2, next: null, previous: null, results: [
      { ...row("Waiting drill"), id: 9, status: "pending_approval", source: "reviewed_request", issued_at: null, closed_at: null, returns: [], returned_at: null },
      row("Returned drill")] });
    state.request.mockImplementation((path: string, init?: RequestInit) => path === "/auth/me" ? Promise.resolve({ id: state.actor })
      : init?.method === "POST" ? Promise.resolve({ id: 9, status: "cancelled", closed_at: "2026-11-03T10:00:00Z" }) : read(path));
    show();
    await screen.findByText("Waiting drill");
    expect(screen.getAllByRole("button", { name: "Withdraw" })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw request" }));
    await waitFor(() => expect(state.request).toHaveBeenCalledWith("/member/makerspaces/7/requests/9/withdraw", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("Request withdrawn.")).toBeVisible();
  });

  it("offers no withdraw while the space has withdrawals switched off", async () => {
    read = () => Promise.resolve({ count: 1, next: null, previous: null, results: [{ ...row("Waiting drill"), status: "accepted", source: "reviewed_request" }] });
    show();
    await screen.findByText("Waiting drill");
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });

  it("shows an account-only borrower's waitlist places, which have no member-area tab without membership", async () => {
    state.extraFeatures = ["loans.waitlist"];
    state.request.mockImplementation((path: string) => path === "/auth/me" ? Promise.resolve({ id: state.actor })
      : path === "/member/makerspaces/7/waitlist" ? Promise.resolve([{ id: 3, product: 8, product_name: "Laser cutter key", quantity: 1,
        status: "waiting", position: 2, offered_at: null, offer_expires_at: null, created_at: "2026-11-01T10:00:00Z" }]) : read(path));
    show();
    expect(await screen.findByText("Laser cutter key ×1")).toBeVisible();
    expect(screen.getByText("Number 2 in line")).toBeVisible();
    expect(screen.getByRole("button", { name: "Leave" })).toBeVisible();
  });

  it("does not read the waitlist while the space has it switched off", async () => {
    show();
    await screen.findByText("Owned drill");
    expect(state.request.mock.calls.some(([path]) => String(path).endsWith("/waitlist"))).toBe(false);
  });
});
