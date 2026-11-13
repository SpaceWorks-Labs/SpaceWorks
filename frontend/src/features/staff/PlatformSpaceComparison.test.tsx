import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { compareSpaces, PlatformSpaceComparison } from "./PlatformSpaceComparison";

const request = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: request }));

const rows = [
  { makerspace_id: 1, metric: "loans", unit: "count", value: 3 },
  { makerspace_id: 1, metric: "loans", unit: "count", value: 2 },
  { makerspace_id: 2, metric: "loans", unit: "count", value: 4 },
  { makerspace_id: 2, metric: "bookings", unit: "count", value: 1 },
  { makerspace_id: 2, metric: "revenue", unit: "minor_currency", value: 900, currency: "INR" },
  { makerspace_id: 1, metric: "makerspace_growth", unit: "count", value: 1 },
  { makerspace_id: null, metric: "app_registrations", unit: "count", value: 7 },
];
const spaces = [{ id: 1, name: "Alpha", slug: "alpha", reports_enabled: true },
  { id: 2, name: "Beta", slug: "beta", reports_enabled: false }];

describe("compareSpaces", () => {
  it("totals counted metrics per space and across spaces", () => {
    const result = compareSpaces(rows, spaces);
    expect(result.metrics).toEqual(["bookings", "loans"]);
    expect(result.rows.map(row => [row.name, row.values])).toEqual([
      ["Alpha", { loans: 5 }], ["Beta", { loans: 4, bookings: 1 }], ["Totals", { loans: 9, bookings: 1 }],
    ]);
  });

  it("is empty without per-space counts", () => {
    expect(compareSpaces([], spaces).rows).toEqual([]);
  });
});

describe("PlatformSpaceComparison", () => {
  it("links only spaces with Reports enabled without removing the other spaces or totals", async () => {
    request.mockResolvedValue({ typed_rows: rows });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <PlatformSpaceComparison period={{ start: "", end: "", grain: "day" }} spaces={spaces} /></QueryClientProvider>);
    expect(await screen.findByRole("link", { name: "Open reports" })).toHaveAttribute("href", "/admin/reports?space=alpha&context=platform");
    expect(screen.getAllByText("Beta").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Totals").length).toBeGreaterThan(0);
  });
});
