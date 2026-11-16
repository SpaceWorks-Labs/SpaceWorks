import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { KeyValueCard } from "./KeyValueCard";
import { expectNoA11yViolations } from "../../test/axe";

it("KeyValueCard renders its contract and remains accessible", async () => {
  
  const { container } = render(<KeyValueCard items={[{label:"Issued",value:"5 / 120"}]} />);
  expect(screen.getByRole("region",{name:"At a glance"})).toBeVisible();
  expect(screen.getByRole("term")).toHaveTextContent("Issued");
  expect(screen.getByRole("definition")).toHaveTextContent("5 / 120");
  await expectNoA11yViolations(container);
});
