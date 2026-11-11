import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ErrorBlock } from "./ErrorBlock";
import { expectNoA11yViolations } from "../../test/axe";

it("ErrorBlock renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<ErrorBlock error={new Error("Network unavailable")} resource="inventory" onRetry={click} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load inventory. Try again.");
  fireEvent.click(screen.getByRole("button",{name:"Retry"}));
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});

it("preserves legacy error detail and hides non-errors", () => {
  const { container, rerender } = render(<ErrorBlock error={new Error("Permission changed")} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Permission changed");
  rerender(<ErrorBlock error={null} />);
  expect(container).toBeEmptyDOMElement();
});
