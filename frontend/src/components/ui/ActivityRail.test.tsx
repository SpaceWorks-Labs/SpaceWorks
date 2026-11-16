import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ActivityRail } from "./ActivityRail";
import { expectNoA11yViolations } from "../../test/axe";

it("ActivityRail renders its contract and remains accessible", async () => {
  
  const { container } = render(<ActivityRail href="/audit"><li>Meera returned a drill.</li></ActivityRail>);
  expect(screen.getByRole("complementary",{name:"Recent activity"})).toBeVisible();
  expect(screen.getByRole("link")).toHaveAttribute("href","/audit");
  await expectNoA11yViolations(container);
});
