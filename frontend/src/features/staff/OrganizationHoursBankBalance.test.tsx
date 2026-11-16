import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { OrganizationHoursBankBalance } from "./OrganizationHoursBankBalance";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));

const bank = { organization_id: 5, makerspace_id: 2, makerspace_name: "Alpha Lab", configured: true, allowance_minutes: 600, period: "monthly",
  period_key: "2030-01", period_ends_at: "2030-02-01T00:00:00+00:00", pool_minutes: 600, used_minutes: 120, remaining_minutes: 480 };
const ledger = { count: 1, next: null, previous: null, results: [{ id: 1, entry: "consume", minutes: -120, period_key: "2030-01", booking_id: 9,
  reason: "", created_at: "2030-01-02T10:00:00Z" }] };

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <OrganizationHoursBankBalance organizationId={5} /></QueryClientProvider>);

beforeEach(() => { mock.request.mockReset(); });

describe("OrganizationHoursBankBalance (OR-13)", () => {
  it("shows a loading state, then the balance", async () => {
    let finish: (value: unknown) => void = () => undefined;
    mock.request.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    show();
    expect(screen.getByRole("status")).toHaveTextContent("Loading hours balance…");
    finish({ banks: [bank] });
    expect(await screen.findByText(/8 h left of 10 h/)).toBeInTheDocument();
  });

  it("says when the balance could not load and retries it", async () => {
    mock.request.mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ banks: [bank] });
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load the hours balance. Try again.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/8 h left of 10 h/)).toBeInTheDocument();
  });

  it("renders nothing for someone who is not an organization admin (404)", async () => {
    mock.request.mockRejectedValue(new StructuredApiError(404, { detail: "Not found." }));
    const view = show();
    await vi.waitFor(() => expect(mock.request).toHaveBeenCalled());
    await vi.waitFor(() => expect(view.container).toBeEmptyDOMElement());
  });

  it("shows the ledger's own error with a retry", async () => {
    let ledgerCalls = 0;
    mock.request.mockImplementation(async (path: string) => {
      if (!path.includes("/ledger/")) return { banks: [bank] };
      ledgerCalls += 1;
      if (ledgerCalls === 1) throw new Error("offline");
      return ledger;
    });
    show();
    fireEvent.click(await screen.findByText("Hours ledger for Alpha Lab"));
    expect(await screen.findByText("Couldn't load the hours ledger. Try again.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/booking 9/)).toBeInTheDocument();
  });
});
