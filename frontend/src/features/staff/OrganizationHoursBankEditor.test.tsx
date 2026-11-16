import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { OrganizationHoursBankBalance } from "./OrganizationHoursBankBalance";
import { OrganizationHoursBankEditor } from "./OrganizationHoursBankEditor";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));

const bank = { organization_id: 5, makerspace_id: 2, configured: true, allowance_minutes: 600, period: "monthly",
  period_key: "2030-01", period_ends_at: "2030-02-01T00:00:00+00:00", pool_minutes: 600, used_minutes: 120, remaining_minutes: 480 };
const row = { id: 1, entry: "consume", minutes: -120, period_key: "2030-01", booking_id: 9, reason: "", actor_name: "Ada",
  created_at: "2030-01-02T10:00:00Z" };
const page = { count: 1, next: null, previous: null, results: [row] };

const wrap = (node: React.ReactNode) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

beforeEach(() => {
  mock.request.mockReset();
  mock.request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (init?.method === "PATCH") return bank;
    if (init?.method === "POST") return { ...row, id: 2, entry: "grant", minutes: 60, reason: "Sponsorship" };
    if (path.includes("/ledger/")) return page;
    if (path === "/admin/organizations/5/hours-bank/") return { banks: [{ ...bank, makerspace_name: "Alpha Lab" }] };
    return bank;
  });
});

it("shows the balance and ledger and saves the allowance in minutes", async () => {
  wrap(<OrganizationHoursBankEditor makerspaceId={2} organizationId={5} />);
  expect(await screen.findByText(/8 h left of 10 h/)).toBeInTheDocument();
  expect(await screen.findByText(/booking 9/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Allowance (hours per period)"), { target: { value: "12.5" } });
  fireEvent.change(screen.getByLabelText("Resets"), { target: { value: "yearly" } });
  fireEvent.click(screen.getByRole("button", { name: "Save allowance" }));
  await waitFor(() => expect(mock.request).toHaveBeenCalledWith("/admin/makerspace/2/organizations/5/hours-bank/", {
    method: "PATCH", body: JSON.stringify({ allowance_minutes: 750, period: "yearly" }) }));
});

it("needs a reason before a grant and sends a positive adjustment as a grant", async () => {
  wrap(<OrganizationHoursBankEditor makerspaceId={2} organizationId={5} />);
  const add = await screen.findByRole("button", { name: "Add to ledger" });
  fireEvent.change(screen.getByLabelText("Grant or adjust (hours, negative to remove)"), { target: { value: "1" } });
  expect(add).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Sponsorship" } });
  fireEvent.click(add);
  await waitFor(() => expect(mock.request).toHaveBeenCalledWith("/admin/makerspace/2/organizations/5/hours-bank/ledger/", {
    method: "POST", body: JSON.stringify({ entry: "grant", minutes: 60, reason: "Sponsorship" }) }));
});

it("tells staff when no allowance exists and hides the adjust form", async () => {
  mock.request.mockImplementation(async (path: string) => path.includes("/ledger/") ? { ...page, results: [] }
    : { ...bank, configured: false, allowance_minutes: 0, pool_minutes: 0, remaining_minutes: 0, period: "none", period_ends_at: null });
  wrap(<OrganizationHoursBankEditor makerspaceId={2} organizationId={5} />);
  expect(await screen.findByText(/No allowance set yet/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Add to ledger" })).not.toBeInTheDocument();
});

it("gives an organization admin a read-only balance without actor names", async () => {
  wrap(<OrganizationHoursBankBalance organizationId={5} />);
  expect(await screen.findByText("Alpha Lab")).toBeInTheDocument();
  expect(screen.getByText(/8 h left of 10 h/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save allowance" })).not.toBeInTheDocument();
});
