import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { MemberIncludedHours } from "./MemberDashboardSections";

const row = { kind: "booking" as const, term_id: 4, plan_name: "Studio plan", term_starts_at: "2026-11-01T00:00:00Z",
  term_ends_at: "2026-12-01T00:00:00Z", allowance_minutes: 600, used_minutes: 150, remaining_minutes: 450 };

it("shows each included-hours pool with what is left this term", () => {
  render(<MemberIncludedHours rows={[row, { ...row, kind: "machine", allowance_minutes: 120, used_minutes: 120, remaining_minutes: 0 }]} />);
  expect(screen.getByRole("heading", { name: "Included hours" })).toBeInTheDocument();
  expect(screen.getByText("7.5 of 10 h left")).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Room bookings: 7.5 of 10 hours left" })).toHaveAttribute("aria-valuenow", "75");
  expect(screen.getByRole("progressbar", { name: "Machine time: 0 of 2 hours left" })).toHaveAttribute("aria-valuenow", "0");
  expect(screen.getAllByText(/Studio plan · resets after/)).toHaveLength(2);
});

it("renders nothing when the plan includes no hours", () => {
  const { container } = render(<MemberIncludedHours rows={[{ ...row, allowance_minutes: 0, remaining_minutes: 0 }]} />);
  expect(container).toBeEmptyDOMElement();
  render(<MemberIncludedHours rows={undefined} />);
  expect(screen.queryByText("Included hours")).toBeNull();
});
