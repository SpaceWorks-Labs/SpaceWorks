import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { OverflowMenu } from "./OverflowMenu";
import { expectNoA11yViolations } from "../../test/axe";

it("OverflowMenu renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<OverflowMenu actions={[{label:"Archive",onClick:click},{label:"Delete",disabled:true},{label:"View",href:"/view"}]} />);
  const trigger=screen.getByRole("button");
  trigger.focus();
  fireEvent.keyDown(trigger,{key:"ArrowDown"});
  expect(screen.getByRole("menuitem",{name:"Archive"})).toHaveFocus();
  fireEvent.keyDown(screen.getByRole("menu"),{key:"End"});
  expect(screen.getByRole("menuitem",{name:"View"})).toHaveFocus();
  fireEvent.keyDown(screen.getByRole("menu"),{key:"d"});
  expect(screen.getByRole("menuitem",{name:"Delete"})).toHaveFocus();
  fireEvent.click(document.activeElement!);
  expect(click).not.toHaveBeenCalled();
  await expectNoA11yViolations(container);
});
