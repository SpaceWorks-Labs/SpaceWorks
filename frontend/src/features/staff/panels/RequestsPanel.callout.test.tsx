import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { StaffListContext } from "../StaffListContext";
import { RequestsPanel } from "./RequestsPanel";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request }));
const empty = { count: 0, next: null, previous: null, results: [] };
function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/admin/requests"]}><StaffListContext.Provider value={{ ownerName: "Desk", canShare: false, actions: ["accept_request"] }}>
      <RequestsPanel makerspace={{ id: 7 } as never} guestOnly={false} canSeeHardware canViewAudit={false} />
    </StaffListContext.Provider></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { request.mockReset(); });
it("announces unresolved kiosk failures and opens the section on demand", async () => {
  request.mockImplementation((path: string) => Promise.resolve(path.includes("kiosk-replays") ? { ...empty, count: 2 } : empty));
  mount();
  expect(await screen.findByText("2 failed kiosk handovers need review.")).toBeVisible();
  const toggle = screen.getByRole("button", { name: /Failed kiosk handovers · 2/ });
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(screen.getByRole("button", { name: "Review failures →" }));
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(request.mock.calls.filter(([path]) => String(path).includes("kiosk-replays"))).toHaveLength(1);
});
it("stays quiet when nothing failed", async () => {
  request.mockResolvedValue(empty);
  mount();
  expect(await screen.findByRole("button", { name: /Failed kiosk handovers · 0/ })).toBeVisible();
  expect(screen.queryByText(/need review/)).not.toBeInTheDocument();
});
