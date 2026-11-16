import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Metric } from "./Metric";
import { expectNoA11yViolations } from "../../test/axe";

it("Metric renders its contract and remains accessible", async () => {
  
  const { container } = render(<Metric label="Overdue" value={0} danger />);
  expect(screen.getByText("0")).toHaveClass("text-ink");
  expect(screen.getByText("Action needed")).toBeVisible();
  await expectNoA11yViolations(container);
});
