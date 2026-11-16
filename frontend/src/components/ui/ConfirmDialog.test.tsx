import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { expectNoA11yViolations } from "../../test/axe";

it("ConfirmDialog renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<ConfirmDialog open title="Delete item?" message="This permanently removes the item." confirmLabel="Delete item" tone="danger" onConfirm={click} onCancel={click} />);
  expect(screen.getByRole("button",{name:"Cancel"})).toHaveClass("desk-button");
  fireEvent.click(screen.getByRole("button",{name:"Delete item"}));
  fireEvent.keyDown(document,{key:"Escape"});
  expect(click).toHaveBeenCalledTimes(2);
  await expectNoA11yViolations(container);
});
