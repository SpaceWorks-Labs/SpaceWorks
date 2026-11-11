import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { StatusBadge, statusToneMap } from "./StatusBadge";
import { expectNoA11yViolations } from "../../test/axe";

it("StatusBadge renders its contract and remains accessible", async () => {

  const { container } = render(<StatusBadge status="checked_out" label="Checked out" />);
  expect(screen.getByText("Checked out")).toHaveClass("bg-accent-soft");
  expect(screen.queryByText("checked out")).not.toBeInTheDocument();
  await expectNoA11yViolations(container);
});

it("preserves every status mapping, domain override and caller-provided word", async () => {
  const { container, rerender } = render(<StatusBadge status="draft" label="Draft" />);
  for (const status of Object.keys(statusToneMap)) {
    rerender(<StatusBadge status={status} label={`Label for ${status}`} />);
    expect(screen.getByText(`Label for ${status}`)).toBeVisible();
    expect(screen.queryByText(status.replace(/_/g, " "))).not.toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
  }
  rerender(<StatusBadge status="cancelled" domain="event" label="Cancelled" />);
  expect(screen.getByText("Cancelled")).toHaveClass("text-danger");
  rerender(<StatusBadge status="completed" domain="service" label="Complete" />);
  expect(screen.getByText("Complete")).toHaveClass("bg-success");
  await expectNoA11yViolations(container);
});
