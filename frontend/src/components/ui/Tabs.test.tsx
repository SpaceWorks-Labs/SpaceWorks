import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it } from "vitest";
import { Tabs } from "./Tabs";
import { expectNoA11yViolations } from "../../test/axe";

it("Tabs renders its contract and remains accessible", async () => {
  
  const { container } = render(<Tabs activeKey="upcoming" tabs={[{key:"upcoming",label:"Upcoming",href:"/upcoming"},{key:"drafts",label:"Drafts",href:"/drafts",count:0}]} />);
  const first=screen.getByRole("link",{name:"Upcoming"});
  first.focus();
  expect(first).toHaveAttribute("aria-current","page");
  fireEvent.keyDown(first,{key:"ArrowRight"});
  expect(screen.getByRole("link",{name:"Drafts 0"})).toHaveFocus();
  fireEvent.keyDown(document.activeElement!,{key:"Home"});
  expect(first).toHaveFocus();
  await expectNoA11yViolations(container);
});
