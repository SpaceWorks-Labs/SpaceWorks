import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { StatusPill } from "./StatusPill";
import { expectNoA11yViolations } from "../../test/axe";

it("StatusPill renders its contract and remains accessible", async () => {
  
  const { container } = render(<StatusPill label="Issued" tone="accent" />);
  expect(screen.getByText("Issued")).toHaveClass("bg-accent-soft");
  expect(container.querySelector("svg")).toHaveAttribute("aria-hidden","true");
  await expectNoA11yViolations(container);
});

it("never renders an icon without a word, including an empty label", () => {
  render(<StatusPill label=" " />);
  expect(screen.getByText("Unknown")).toBeVisible();
});
