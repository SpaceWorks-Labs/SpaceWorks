import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { StaffListContext } from "../StaffListContext";
import { Queues } from "./Queues";
import { expectNoA11yViolations } from "../../../test/axe";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
vi.mock("./QueuesModals", () => ({ AssignIssueModal: () => null, RejectRequestModal: () => null, ReturnDueModal: () => null, ReturnRequestModal: () => null }));
vi.mock("./QueuesAcceptModal", () => ({ AcceptRequestModal: () => null }));
const empty = { count: 0, results: [] };
const row = { id: 42, requester_username: "ada", requester_display: "Ada", status: "issued", requested_for: "Robotics club",
  return_due_at: null, return_reminder_sent_at: null, items: [{ id: 1, product_name: "Drill", requested_quantity: 2, accepted_quantity: 2, issued_quantity: 2, storage_location: "Shelf B3" }] };
const queueCalls = () => request.mock.calls.filter(([path]) => /\/(pending-requests|accepted-requests|active-loans|request-history)\?/.test(path));
function Location() { const value = useLocation(); return <output data-testid="location">{value.search}</output>; }
function mount(url: string, actions = ["accept_request", "issue_request"], guestOnly = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><StaffListContext.Provider value={{ ownerName: "Desk", canShare: false, actions }}>
      <Queues makerspace={{ id: 7 } as never} guestOnly={guestOnly} /><Location />
    </StaffListContext.Provider></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { request.mockReset(); request.mockResolvedValue(empty); });
it.each([["", "pending-requests", "Pending review"], ["?queue=active", "active-loans", "Active loans"], ["?history=true", "request-history", "History"], ["?activePage=3", "active-loans", "Active loans"]])("fetches only the selected queue at %s", async (search, endpoint, label) => {
  const { container } = mount(`/admin/requests${search}`);
  await waitFor(() => expect(queueCalls()).toHaveLength(1));
  expect(queueCalls()[0][0]).toContain(`/${endpoint}?`);
  expect(screen.getByRole("link", { name: label })).toHaveAttribute("aria-current", "page");
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  await expectNoA11yViolations(container);
});
it("keeps hidden queues out of both navigation and network requests", async () => {
  mount("/admin/requests?queue=pending", ["issue_request"], true);
  await waitFor(() => expect(queueCalls()).toHaveLength(1));
  expect(queueCalls()[0][0]).toContain("accepted-requests");
  expect(screen.queryByRole("link", { name: "Pending review" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Active loans" })).toHaveAttribute("href", "/admin/requests?queue=active");
  expect(queueCalls().some(([path]) => path.includes("pending-requests") || path.includes("active-loans"))).toBe(false);
});
it("probes id on page one without stale search/order and opens the found request despite another probe failing", async () => {
  request.mockImplementation((path: string) => path.includes("pending-requests") ? Promise.reject(new Error("Forbidden"))
    : Promise.resolve(path.includes("active-loans") ? { count: 1, results: [row] } : empty));
  mount("/admin/requests?id=42&history=true&activePage=3&search=wrong&ordering=created_at");
  expect(await screen.findByRole("dialog", { name: "Request #42" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Active loans" })).toHaveAttribute("aria-current", "page");
  expect(queueCalls()).toHaveLength(4);
  queueCalls().forEach(([path]) => { expect(path).toContain("page=1&"); expect(path).toContain("id=42"); expect(path).not.toContain("search="); expect(path).not.toContain("ordering="); });
});
it("probes only the pending queue for an accept-only reviewer", async () => {
  mount("/admin/requests?id=999", ["accept_request"]);
  expect(await screen.findByText("We couldn't find request #999 in your queues.")).toBeVisible();
  expect(queueCalls()).toHaveLength(1);
  expect(queueCalls()[0][0]).toContain("pending-requests");
});
it("distinguishes failed probes from not found and retries them", async () => {
  request.mockImplementation((path: string) => path.includes("-requests?") || path.includes("active-loans?") || path.includes("request-history?") ? Promise.reject(new Error("Network error")) : Promise.resolve(empty));
  mount("/admin/requests?id=42");
  expect(await screen.findByText("Couldn't open request #42. Try again.")).toBeVisible();
  expect(screen.queryByText("We couldn't find request #42 in your queues.")).not.toBeInTheDocument();
  request.mockResolvedValue(empty); fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("We couldn't find request #42 in your queues.")).toBeVisible();
});
it("preserves filters, clears legacy history and resets page keys on tab click", async () => {
  mount("/admin/requests?queue=pending&pendingPage=2&search=ada&ordering=created_at&history=true");
  fireEvent.click(screen.getByRole("link", { name: "Ready for handover" }));
  await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("queue=accepted"));
  const url = screen.getByTestId("location").textContent!;
  expect(url).toContain("search=ada"); expect(url).toContain("ordering=created_at"); expect(url).not.toContain("Page="); expect(url).not.toContain("history=");
});
it("moves shelf details to the drawer and loads private evidence only on request", async () => {
  request.mockImplementation((path: string) => Promise.resolve(path.includes("/evidence/9") ? { url: "https://private.test/signed" }
    : path.includes("active-loans") ? { count: 1, results: [{ ...row, issue_evidence_id: 9 }] } : empty));
  mount("/admin/requests?queue=active");
  await screen.findByText("Robotics club"); expect(screen.queryByText(/Shelf B3/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Ada/ }));
  const drawer = await screen.findByRole("dialog", { name: "Request #42" });
  expect(within(drawer).getByText(/Shelf B3/)).toBeVisible();
  fireEvent.click(within(drawer).getByRole("link", { name: "Evidence" }));
  expect(request.mock.calls.some(([path]) => path.includes("/evidence/"))).toBe(false);
  fireEvent.click(within(drawer).getByRole("button", { name: "View issue photo" }));
  expect(await within(drawer).findByAltText("Issue photo")).toHaveAttribute("src", "https://private.test/signed");
});

it("shows shelves on ready rows and flags damaged or missing units on the row", async () => {
  request.mockImplementation((path: string) => Promise.resolve(path.includes("accepted-requests") ? { count: 1, results: [{ ...row, status: "accepted" }] }
    : path.includes("active-loans") ? { count: 1, results: [{ ...row, items: [{ ...row.items[0], damaged_quantity: 1, missing_quantity: 2 }] }] } : empty));
  const view = mount("/admin/requests?queue=accepted");
  expect(await screen.findByText("Shelf: Shelf B3")).toBeVisible();
  view.unmount();
  mount("/admin/requests?queue=active");
  expect(await screen.findByText("1 damaged · 2 missing")).toBeVisible();
});

it("clears an unmatched new drawer link as well as legacy id filters", async () => {
  mount("/admin/requests?request=999");
  expect(await screen.findByText("We couldn't find request #999 in your queues.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  await waitFor(() => expect(screen.getByTestId("location").textContent).not.toContain("request="));
  await waitFor(() => expect(queueCalls().some(([path]) => path.includes("pending-requests?") && !path.includes("id="))).toBe(true));
});
it("reports clipboard success and handles permission rejection", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  request.mockImplementation((path: string) => Promise.resolve(path.includes("active-loans") ? { count: 1, results: [row] } : empty));
  mount("/admin/requests?queue=active");
  await screen.findByText("Robotics club");
  fireEvent.click(screen.getByRole("button", { name: "More actions for request #42" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Copy link" }));
  expect(await screen.findByText("Request link copied.")).toBeVisible();
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("id=42"));
  writeText.mockRejectedValue(new Error("Permission denied"));
  fireEvent.click(screen.getByRole("button", { name: "More actions for request #42" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Copy link" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't copy the link.");
  Reflect.deleteProperty(navigator, "clipboard");
});

it("offers an All queues view that stacks only the queues the actor may see", async () => {
  request.mockImplementation((path: string) => Promise.resolve(path.includes("active-loans") ? { count: 30, results: [row] }
    : path.includes("accepted-requests") ? { count: 1, results: [{ ...row, id: 43, status: "accepted" }] } : empty));
  mount("/admin/requests?queue=all", ["issue_request"]);
  expect(await screen.findByRole("region", { name: "Active loans" })).toBeVisible();
  expect(screen.getByRole("link", { name: "All queues" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("region", { name: "Ready for handover" })).toBeVisible();
  expect(screen.queryByRole("region", { name: "Pending review" })).not.toBeInTheDocument();
  expect(queueCalls().map(([path]) => path.match(/\/(\w+-?\w*)\?/)![1]).sort()).toEqual(["accepted-requests", "active-loans", "request-history"]);
  expect(screen.getByRole("link", { name: "Show all 30 in Active loans" })).toHaveAttribute("href", expect.stringContaining("queue=active"));
});
it("keeps the per-queue tab as the default and hides All queues for a single-queue actor", async () => {
  mount("/admin/requests", ["accept_request"]);
  await waitFor(() => expect(queueCalls()).toHaveLength(1));
  expect(screen.queryByRole("link", { name: "All queues" })).not.toBeInTheDocument();
});
