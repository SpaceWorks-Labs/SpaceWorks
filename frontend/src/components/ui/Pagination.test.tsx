import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Pagination } from "./Pagination";
import { expectNoA11yViolations } from "../../test/axe";

it("Pagination renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<Pagination page={1} totalPages={3} count={60} pageSize={24} onChange={click} />);
  expect(screen.getByRole("button",{name:"Previous"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button",{name:"Next"}));
  expect(click).toHaveBeenCalledWith(2);
  await expectNoA11yViolations(container);
});
