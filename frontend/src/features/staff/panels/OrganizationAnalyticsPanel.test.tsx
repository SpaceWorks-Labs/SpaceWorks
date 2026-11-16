import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OrganizationReportResponse } from "../organizationAnalyticsApi";
import { OrganizationAnalyticsPanel } from "./OrganizationAnalyticsPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const report: OrganizationReportResponse = {
  report_key: "summary",
  strategy: "sum",
  breakdown: [
    { makerspace_id: 19, rows: [{ products: 2, active_loans: 1 }] },
    { makerspace_id: 20, rows: [{ products: 3, active_loans: 1 }] },
  ],
  total: { rows: [{ products: 5, active_loans: 2 }] },
};

const makerspaces = [
  { id: 19, name: "North workshop" },
  { id: 20, name: "South workshop" },
] as Parameters<typeof OrganizationAnalyticsPanel>[0]["makerspaces"];

function renderPanel(response: OrganizationReportResponse | Promise<never> = report) {
  staffRequest.mockImplementation((path: string) => path.startsWith("/admin/organizations/?")
    ? Promise.resolve({ count: 1, next: null, previous: null, results: [{ id: 7, name: "Workshop network" }] })
    : response instanceof Promise ? response : Promise.resolve(response));
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <OrganizationAnalyticsPanel makerspaces={makerspaces} />
    </QueryClientProvider>,
  );
}

async function selectOrganization(id = "7") {
  await screen.findByRole("option", { name: "Workshop network" });
  fireEvent.change(screen.getByLabelText("Organization"), { target: { value: id } });
}

beforeEach(() => {
  staffRequest.mockReset();
});

describe("OrganizationAnalyticsPanel", () => {
  it("renders the per-makerspace breakdown and organization total together", async () => {
    renderPanel();
    await selectOrganization();

    expect(await screen.findByRole("heading", { name: "Breakdown by makerspace" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "North workshop" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "South workshop" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Organization total" })).toBeVisible();
    for (const [name, products] of [["North workshop", "2"], ["South workshop", "3"], ["Organization total", "5"]]) {
      const section = within(screen.getByRole("heading", { name }).closest("section")!);
      fireEvent.click(section.getByRole("button", { name: "Show report data" }));
      const table = section.getByRole("table");
      expect(table).toBeVisible();
      expect(within(table).getByRole("columnheader", { name: "Products" })).toBeVisible();
      expect(within(table).getByRole("rowheader", { name: products })).toBeVisible();
    }
    expect(staffRequest).toHaveBeenCalledWith("/admin/organizations/7/analytics/summary?");
  });

  it("renders a layout skeleton while the request is pending", async () => {
    renderPanel(new Promise(() => {}));
    await selectOrganization();

    expect(screen.getByLabelText("Loading content")).toBeVisible();
  });

  it("treats an empty breakdown as an empty result rather than an error", async () => {
    renderPanel({ ...report, breakdown: [], total: { rows: [] } });
    await selectOrganization();

    expect(await screen.findByText("This organization doesn't own any spaces with reports yet."))
      .toBeVisible();
    expect(screen.queryByRole("heading", { name: "Unable to load organization analytics" }))
      .not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Organization total" })).toBeVisible();
    expect(screen.getByText("No activity in this period. Try a longer range.")).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows a retryable error state", async () => {
    renderPanel();
    await screen.findByRole("option", { name: "Workshop network" });
    staffRequest.mockRejectedValueOnce(new Error("Network unavailable"));
    await selectOrganization();

    expect(await screen.findByText("Couldn't load organization analytics. Try again.")).toBeVisible();
    staffRequest.mockResolvedValueOnce(report);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(3));
  });

  it("offers aggregate machine-service reports while excluding identity-bearing rankings and legacy printer service", () => {
    renderPanel();
    const selector = screen.getByLabelText("Report");

    expect(within(selector).getByRole("option", { name: "Machine service" })).toBeInTheDocument();
    expect(within(selector).getByRole("option", { name: "Printer jobs" })).toBeInTheDocument();
    expect(within(selector).queryByRole("option", { name: "Printer service" }))
      .not.toBeInTheDocument();
    expect(Array.from((selector as HTMLSelectElement).options, (option) => option.value))
      .toEqual(expect.not.arrayContaining(["top-borrowers"]));
  });
});
