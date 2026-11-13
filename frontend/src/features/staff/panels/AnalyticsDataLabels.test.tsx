import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { AnalyticsData } from "./AnalyticsData";

const rows = [
  { makerspace_id: 7, metric: "members_without_card", value: 3 },
  { makerspace_id: 7, metric: "auto_issued", value: 1 },
];

it("shows metric names in words and drops a space-id column that is the same on every row", () => {
  render(<AnalyticsData title="Cards" rows={rows} />);
  fireEvent.click(screen.getByRole("button", { name: "Show report data" }));
  expect(screen.queryByRole("columnheader", { name: "Space ID" })).not.toBeInTheDocument();
  expect(screen.getByText("Members without card")).toBeInTheDocument();
  expect(screen.queryByText("members_without_card")).not.toBeInTheDocument();
  expect(screen.getByText("Auto issued")).toBeInTheDocument();
});

it("keeps the space-id column when rows come from different spaces", () => {
  render(<AnalyticsData title="Cards" rows={[{ ...rows[0] }, { ...rows[1], makerspace_id: 8 }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Show report data" }));
  expect(screen.getByRole("columnheader", { name: "Space ID" })).toBeInTheDocument();
});
