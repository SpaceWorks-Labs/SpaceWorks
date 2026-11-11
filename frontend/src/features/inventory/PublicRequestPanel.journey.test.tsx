/** Inventory journey (0.12.0): the borrow panel tells each requester the rule that applies to them. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { PublicRequestPanel } from "./PublicRequestPanel";

const mock = vi.hoisted(() => ({ owner: "1" as string | null, scanProps: vi.fn() }));
vi.mock("./useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: mock.owner }) }));
vi.mock("../../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => Boolean(mock.owner), getSessionOwner: () => mock.owner }));
vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), memberRequest: vi.fn().mockResolvedValue({ id: 1 }) }));
vi.mock("./api", () => ({ submitPublicRequest: vi.fn(), requestContactCode: vi.fn() }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));
vi.mock("./PublicToolScanPanel", () => ({ PublicToolScanPanel: (props: { borrowOff?: boolean }) => { mock.scanProps(props); return <p>Scan panel</p>; } }));

const items = [{ productId: 4, name: "Drill", quantity: 1 }];
function setup(props: Partial<Parameters<typeof PublicRequestPanel>[0]>) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <PublicRequestPanel items={items} makerspaceSlug="forge" onClear={vi.fn()} {...props} /></QueryClientProvider>);
}
beforeEach(() => { mock.owner = "1"; mock.scanProps.mockReset(); });

it("does not tell an account-only borrower they need a membership", () => {
  setup({ modules: ["request_workflow"], features: ["inventory.self_checkout"] });
  expect(screen.getByText("Requests use your signed-in account. Staff review every request before anything is handed over.")).toBeVisible();
  expect(screen.queryByText(/An active membership/)).toBeNull();
});

it("keeps the membership rule where the membership module is on", () => {
  setup({ modules: ["request_workflow", "membership"], features: [] });
  expect(screen.getByRole("heading", { name: "Member borrowing" })).toBeVisible();
  expect(screen.getByText(/An active membership, waiver acceptance/)).toBeVisible();
});

it("gives a signed-out visitor a way to sign in instead of a silently disabled form", () => {
  mock.owner = null;
  // 0.12.0 row 29: the member sign-in returns here (`next`) and the cart rides along in sessionStorage.
  window.history.replaceState(null, "", "/m/forge/inventory?category=3");
  setup({ modules: ["request_workflow"], features: [] });
  const link = screen.getAllByRole("link", { name: "Sign in to borrow" }).at(-1)!;
  expect(link).toHaveAttribute("href", `/m/forge/member?next=${encodeURIComponent("/m/forge/inventory?category=3")}`);
  link.addEventListener("click", event => event.preventDefault());
  fireEvent.click(link);
  expect(JSON.parse(window.sessionStorage.getItem("spaceworks.publicCart.handoff:/m/forge/inventory") ?? "[]")).toEqual(items);
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/");
});

it("asks no one to sign in on the account-less contact path", () => {
  mock.owner = null;
  setup({ requestAccess: "contact", features: [] });
  expect(screen.queryByRole("link", { name: "Sign in to borrow" })).toBeNull();
});

it("hides Scan a tool while self-checkout is off, even when the page asks for it", () => {
  setup({ modules: ["request_workflow"], features: [], activeTab: "scan" });
  expect(screen.queryByRole("radio", { name: "Scan a tool" })).toBeNull();
  expect(screen.queryByText("Scan panel")).toBeNull();
});

it("tells the scan panel when account-less checkout is off so it offers returns only", () => {
  setup({ requestAccess: "contact", features: ["inventory.self_checkout"], activeTab: "scan" });
  expect(screen.getByRole("heading", { name: "Borrow or return a tool" })).toBeVisible();
  expect(mock.scanProps).toHaveBeenLastCalledWith(expect.objectContaining({ borrowOff: true }));
});

it("lets account-less checkout through when its switch is on", () => {
  setup({ requestAccess: "contact", features: ["inventory.self_checkout", "inventory.contact_self_checkout"], activeTab: "scan" });
  expect(mock.scanProps).toHaveBeenLastCalledWith(expect.objectContaining({ borrowOff: false }));
});
