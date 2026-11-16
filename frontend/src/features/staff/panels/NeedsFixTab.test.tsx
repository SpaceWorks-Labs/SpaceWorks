import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { NeedsFixTab } from "./NeedsFixTab";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

const space = { id: 7, name: "Forge", public_code: "forge", slug: "forge", telegram_group_chat_id: "", frontend_domain: null,
  hidden_from_central_directory: false };
const report = { id: 4, requester_username: "ada", label: "Drill", note: "Chuck wobbles", created_at: "2026-11-01T10:00:00Z",
  items: [{ id: 9, product_name: "Drill", issued_quantity: 1, tracking_mode: "quantity" }] };

function mount(url: string, modules?: string[]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><NeedsFixTab makerspace={{ ...space, enabled_modules: modules }} /></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string) => Promise.resolve(path.includes("problem-reports")
    ? { results: [report], truncated: false } : { results: [] }));
});

describe("NeedsFixTab (final audit 0.12.0, decision 224 a)", () => {
  it("lists open problem reports from the inventory-area route on ?section=problems", async () => {
    mount("/m/forge/admin/to-be-fixed?section=problems", ["staff_admin", "reports"]);
    expect(await screen.findByText("Chuck wobbles", { selector: "span" })).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/problem-reports");
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspace/7/accountability");
  });

  it("shows the shelf by default and hides the problem-report tab without the reports module", async () => {
    mount("/m/forge/admin/to-be-fixed?section=problems", ["staff_admin"]);
    expect(await screen.findByText("Repair shelf", { selector: "h1" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Problem reports/ })).toBeNull();
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspace/7/problem-reports");
  });
});
