import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { DateChip } from "./DateChip";
import { expectNoA11yViolations } from "../../test/axe";

it("DateChip renders its contract and remains accessible", async () => {
  
  const { container } = render(<DateChip date="2026-10-14" />);
  expect(screen.getByText("Oct")).toBeVisible();
  expect(screen.getByText("14")).toBeVisible();
  await expectNoA11yViolations(container);
});

it("keeps calendar dates stable, mutes drafts, and handles an invalid date", () => {
  const { rerender } = render(<DateChip date="2026-10-14" draft />);
  expect(screen.getByText("14")).toBeVisible();
  expect(screen.getByText("Oct")).toHaveClass("bg-surface");
  rerender(<DateChip date="invalid" />);
  expect(screen.getByText("Unknown date")).toBeVisible();
});
