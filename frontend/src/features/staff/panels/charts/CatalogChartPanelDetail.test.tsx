import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { CatalogChartPanel } from "./CatalogChartPanel";

const rows = [
  { makerspace_id: 25, metric: "active_cards", value: 0 },
  { makerspace_id: 25, metric: "members_without_card", value: 1 },
];

it("a detail report (no measures) reads in words and drops the repeated space id", () => {
  render(<CatalogChartPanel title="Member card issuance" rows={rows} spec={{ values: [] } as never} />);
  expect(screen.queryByRole("columnheader", { name: "Space ID" })).not.toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Metric" })).toBeInTheDocument();
  expect(screen.getByText(/Members without card/)).toBeInTheDocument();
  expect(screen.queryByText(/active_cards/)).not.toBeInTheDocument();
});
