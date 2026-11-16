import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { EmptyState } from "./EmptyState";
import { expectNoA11yViolations } from "../../test/axe";

it("EmptyState renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<EmptyState message="No parts yet. Add your first item." action={{label:"Add item",onClick:click}} />);
  expect(container.firstChild).toHaveClass("border-dashed", "border-line", "rounded-2xl");
  expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button"));
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});

it("keeps legacy heading and separate description queries working", async () => {
  const { container } = render(<EmptyState title="No items" description="Add your first item above." action={<button>Add item</button>} />);
  expect(screen.getByRole("heading", {name:"No items"})).toBeVisible();
  expect(screen.getByText("Add your first item above.")).toBeVisible();
  await expectNoA11yViolations(container);
});
