import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Modal } from "./Modal";
import { expectNoA11yViolations } from "../../test/axe";

it("Modal renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<Modal open onClose={click} title="Edit name"><input aria-label="Name" /><button>Save</button></Modal>);
  expect(screen.getByRole("dialog",{name:"Edit name"})).toBeVisible();
  expect(screen.getByRole("textbox")).toHaveFocus();
  fireEvent.keyDown(document,{key:"Escape"});
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
