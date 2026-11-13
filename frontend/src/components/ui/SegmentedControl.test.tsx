import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SegmentedControl } from "./SegmentedControl";
import { expectNoA11yViolations } from "../../test/axe";

it("SegmentedControl renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<SegmentedControl label="View" value="page" onChange={click} options={[{value:"page",label:"Page"},{value:"programme",label:"Programme"}]} />);
  const page=screen.getByRole("radio",{name:"Page"});
  page.focus();
  expect(page).toHaveAttribute("aria-checked","true");
  fireEvent.keyDown(page,{key:"ArrowRight"});
  expect(screen.getByRole("radio",{name:"Programme"})).toHaveFocus();
  expect(click).toHaveBeenCalledWith("programme");
  await expectNoA11yViolations(container);
});
