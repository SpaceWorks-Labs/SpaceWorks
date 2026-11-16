import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { StatCard } from "./StatCard";
import { expectNoA11yViolations } from "../../test/axe";

it("StatCard renders its contract and remains accessible", async () => {
  
  const { container } = render(<StatCard label="Waiting" value={0} of={120} progress={0} tone="attention" href="/requests" />);
  expect(screen.getByRole("link")).toHaveAttribute("href","/requests");
  expect(screen.getByText("Needs attention")).toHaveClass("bg-emphasis");
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow","0");
  await expectNoA11yViolations(container);
});
