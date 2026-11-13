import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ActivityItem } from "./ActivityItem";
import { expectNoA11yViolations } from "../../test/axe";

it("ActivityItem renders its contract and remains accessible", async () => {
  
  const { container } = render(<ul><ActivityItem actor="Kiran Reddy" object="Demo Summit" date="2026-10-15T12:00:00Z">joined the waitlist</ActivityItem></ul>);
  expect(screen.getByText("Kiran Reddy").tagName).toBe("STRONG");
  expect(screen.getByText("Demo Summit").tagName).toBe("STRONG");
  await expectNoA11yViolations(container);
});
