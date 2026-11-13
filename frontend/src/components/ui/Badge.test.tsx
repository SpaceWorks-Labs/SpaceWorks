import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Badge } from "./Badge";
import { expectNoA11yViolations } from "../../test/axe";

it("Badge renders its contract and remains accessible", async () => {
  
  const { container } = render(<Badge tone="success">Returned</Badge>);
  expect(screen.getByText("Returned")).toBeVisible();
  expect(container.querySelector("svg")).toBeInTheDocument();
  await expectNoA11yViolations(container);
});
