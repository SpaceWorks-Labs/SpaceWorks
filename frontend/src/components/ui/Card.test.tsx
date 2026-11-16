import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Card } from "./Card";
import { expectNoA11yViolations } from "../../test/axe";

it("Card renders its contract and remains accessible", async () => {
  
  const { container } = render(<Card padding="sm"><p>Card content</p></Card>);
  expect(screen.getByText("Card content")).toBeVisible();
  await expectNoA11yViolations(container);
});
