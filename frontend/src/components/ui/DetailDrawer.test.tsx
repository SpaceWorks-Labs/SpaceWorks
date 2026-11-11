import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DetailDrawer } from "./DetailDrawer";
import { expectNoA11yViolations } from "../../test/axe";

it("DetailDrawer renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<DetailDrawer open title="Drill" onClose={click}><p>Drill details</p></DetailDrawer>);
  expect(screen.getByRole("dialog",{name:"Drill"})).toBeVisible();
  expect(screen.getByRole("button",{name:"Close"})).toHaveFocus();
  fireEvent.keyDown(document,{key:"Escape"});
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
