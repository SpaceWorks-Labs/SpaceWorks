import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { BulkActionToolbar } from "./BulkActionToolbar";
import { expectNoA11yViolations } from "../../test/axe";

it("BulkActionToolbar renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<BulkActionToolbar selectedCount={3} onClear={click} actions={<button>Archive</button>} />);
  expect(screen.getByRole("status")).toHaveTextContent("3 selected");
  fireEvent.click(screen.getByRole("button",{name:"Clear selection"}));
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
