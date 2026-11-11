import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { StatRow } from "./StatRow";
import { expectNoA11yViolations } from "../../test/axe";

it("StatRow renders its contract and remains accessible", async () => {
  
  const { container } = render(<StatRow stats={[{label:"Issued",value:5},{label:"Returned",value:0}]} />);
  expect(screen.getByText("Issued")).toBeVisible();
  expect(screen.getByText("0")).toBeVisible();
  await expectNoA11yViolations(container);
});
