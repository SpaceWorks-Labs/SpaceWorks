import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AccountabilityPanel } from "./AccountabilityPanel";
import type { Makerspace } from "./shared";
const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"), staffRequest }));
const report = { overdue: [], problem_reports: [], restrictions: [],
  repeat_offenders: [{ requester_id: 5, username: "Ada", access_status: "active", damaged: 1, missing: 0,
    total_issues: 1, total_quantity: 1, restriction_reason: "" }],
  anonymous_accountability: { damaged: 1, missing: 1, total_issues: 2, total_quantity: 2 },
  truncated: { overdue: false, problem_reports: false, repeat_offenders: false } };
describe("accountability tabs", () => {
  it("retains anonymous incidents and requires a reason before restriction", async () => {
    staffRequest.mockResolvedValue(report);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><MemoryRouter>
      <AccountabilityPanel makerspace={{ id: 7, slug: "forge" } as Makerspace} isSuperadmin />
    </MemoryRouter></QueryClientProvider>);
    try {
      // An empty section param means every section, so the offenders are visible without a click.
      expect(await screen.findByRole("heading", { name: "Repeat offenders", level: 2 })).toBeVisible();
      expect(screen.getByRole("link", { name: "All" })).toHaveAttribute("aria-current", "page");
      const nav = screen.getByRole("navigation", { name: "Page sections" });
      fireEvent.click(within(nav).getByRole("link", { name: "Repeat offenders 1" }));
      expect(screen.getByText("Account-less loans")).toBeVisible();
      expect(screen.getByText(/1 damaged, 1 missing/)).toBeVisible();
      fireEvent.click(screen.getByRole("button", { name: "Restrict…" }));
      const dialog = screen.getByRole("dialog", { name: "Restrict requester?" });
      expect(within(dialog).getByRole("button", { name: "Restrict Ada" })).toBeDisabled();
      fireEvent.change(within(dialog).getByLabelText("Reason for restriction"), { target: { value: "Repeated damage" } });
      fireEvent.click(within(dialog).getByRole("button", { name: "Restrict Ada" }));
      await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/users/5/restrict", {
        method: "POST", body: JSON.stringify({ status: "restricted", reason: "Repeated damage" }),
      }));
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    } finally { view.unmount(); client.clear(); }
  });
});
