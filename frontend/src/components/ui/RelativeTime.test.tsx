import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { RelativeTime } from "./RelativeTime";
import { expectNoA11yViolations } from "../../test/axe";

it("RelativeTime renders its contract and remains accessible", async () => {
  
  const { container } = render(<RelativeTime date="2026-10-15T11:58:00" now="2026-10-15T12:00:00" />);
  expect(screen.getByText("2 min ago")).toHaveAttribute("datetime");
  await expectNoA11yViolations(container);
});
