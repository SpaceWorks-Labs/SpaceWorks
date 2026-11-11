import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ProgressBar } from "./ProgressBar";
import { expectNoA11yViolations } from "../../test/axe";

it("ProgressBar renders its contract and remains accessible", async () => {
  
  const { container } = render(<ProgressBar label="Checked in" value={0.42} />);
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow","42");
  await expectNoA11yViolations(container);
});

it.each([[-1, "0"], [2, "100"], [NaN, "0"], [Infinity, "0"]])("bounds progress %s to a valid ARIA value", (value, expected) => {
  render(<ProgressBar label="Progress" value={value} />);
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", expected);
});

it.each(["accent", "warn", "danger"] as const)("uses the %s token without changing progress semantics", tone => {
  render(<ProgressBar label="Allowance used" value={0.85} tone={tone} />);
  const progress = screen.getByRole("progressbar", { name: "Allowance used" });
  expect(progress).toHaveAttribute("aria-valuenow", "85");
  expect(progress.firstElementChild).toHaveClass(`bg-${tone}`);
});

it("keeps the accent fill by default", () => {
  render(<ProgressBar label="Progress" value={0.5} />);
  expect(screen.getByRole("progressbar").firstElementChild).toHaveClass("bg-accent");
});
