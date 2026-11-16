import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FilterBar } from "./FilterBar";
import { expectNoA11yViolations } from "../../test/axe";

it("FilterBar renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<FilterBar value="" onChange={click} searchLabel="Search inventory" actions={<button>Export</button>} />);
  const input=screen.getByRole("searchbox",{name:"Search inventory"});
  input.focus();
  expect(input).toHaveFocus();
  fireEvent.change(input,{target:{value:"drill"}});
  expect(click).toHaveBeenCalledWith("drill");
  await expectNoA11yViolations(container);
});
