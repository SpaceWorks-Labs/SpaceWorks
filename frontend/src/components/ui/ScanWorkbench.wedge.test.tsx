import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScanWorkbench } from "./ScanWorkbench";

it("clears the field and keeps focus after each find so back-to-back wedge scans never append", () => {
  const onFind = vi.fn();
  const { rerender } = render(<ScanWorkbench onFind={onFind} searchLabel="Find a code" />);
  const field = screen.getByRole("searchbox", { name: "Find a code" });
  fireEvent.change(field, { target: { value: "BOX-1" } });
  fireEvent.submit(field.closest("form")!);
  expect(onFind).toHaveBeenLastCalledWith("BOX-1");
  expect(field).toHaveValue("");
  expect(field).toHaveFocus();
  // While the lookup is pending the field is disabled; focus returns when it settles.
  rerender(<ScanWorkbench onFind={onFind} searchLabel="Find a code" findPending />);
  rerender(<ScanWorkbench onFind={onFind} searchLabel="Find a code" findPending={false} />);
  fireEvent.change(field, { target: { value: "BOX-2" } });
  fireEvent.submit(field.closest("form")!);
  expect(onFind).toHaveBeenLastCalledWith("BOX-2");
});
