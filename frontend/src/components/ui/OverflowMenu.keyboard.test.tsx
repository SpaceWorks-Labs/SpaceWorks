import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { OverflowMenu } from "./OverflowMenu";
import { expectNoA11yViolations } from "../../test/axe";

it("closes on Escape, Tab, outside press and activation, restoring focus where needed", async () => {
  const action = vi.fn();
  const { container } = render(<><OverflowMenu actions={[{ label: "Archive", onClick: action }, { label: "View", href: "/view" }]} /><button>Outside</button></>);
  const trigger = screen.getByRole("button", { name: "More actions" });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowUp" });
  expect(screen.getByRole("menuitem", { name: "View" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  expect(trigger).toHaveFocus();
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  fireEvent.click(trigger);
  fireEvent.keyDown(document.activeElement!, { key: "Tab" });
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  fireEvent.click(trigger);
  fireEvent.pointerDown(screen.getByRole("button", { name: "Outside" }));
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("menuitem", { name: "Archive" }));
  expect(action).toHaveBeenCalledOnce();
  expect(trigger).toHaveFocus();
  await expectNoA11yViolations(container);
});

it("activates link menuitems with Space and skips CSS-hidden items", async () => {
  const click = vi.fn();
  const { container } = render(<OverflowMenu actions={[{label:"View",href:"#view",onClick:click}]} mobileActions={[{label:"Mobile"}]} />);
  const hiddenStyle = document.createElement("style");
  hiddenStyle.textContent = ".md\\:hidden { display: none; }";
  container.appendChild(hiddenStyle);
  fireEvent.keyDown(screen.getByRole("button"), {key:"ArrowDown"});
  expect(screen.getByRole("menuitem", {name:"View"})).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, {key:" "});
  expect(click).toHaveBeenCalledOnce();
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  await expectNoA11yViolations(container);
});
