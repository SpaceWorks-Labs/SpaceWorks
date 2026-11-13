import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { KioskPin } from "./KioskPin";

it("defaults to eight code boxes and preserves physical keyboard editing and paste", () => {
  const submit = vi.fn();
  const { container } = render(<KioskPin title="Unlock" helper="Ask staff" pending={false} onSubmit={submit}
    submitLabel="Unlock station" pendingLabel="Unlocking station…" />);
  const input = screen.getByLabelText("Station PIN");
  expect(input).toHaveAttribute("maxlength", "8");
  expect(input).toHaveAttribute("inputmode", "numeric");
  expect(container.querySelectorAll('[aria-hidden="true"] > span')).toHaveLength(8);
  // The one native password input owns typing, selection, Backspace and paste;
  // visual boxes never intercept keyboard events or reveal entered digits.
  fireEvent.change(input, { target: { value: "123" } });
  expect(input).toHaveValue("123");
  fireEvent.input(input, { target: { value: "12" }, inputType: "deleteContentBackward" });
  expect(input).toHaveValue("12");
  fireEvent.input(input, { target: { value: "12345678" }, inputType: "insertFromPaste" });
  expect(input).toHaveValue("12345678");
  fireEvent.click(screen.getByRole("button", { name: "Unlock station" }));
  expect(submit).toHaveBeenCalledWith("12345678");
});

it("supports custom length, numeric normalization, keypad deletion and pending copy", () => {
  const props = { title: "PIN", helper: "Ask staff", length: 4, pending: false, onSubmit: vi.fn(),
    submitLabel: "Unlock station", pendingLabel: "Unlocking station…" };
  const { rerender } = render(<KioskPin {...props} />);
  fireEvent.change(screen.getByLabelText("Station PIN"), { target: { value: "1a23456" } });
  expect(screen.getByLabelText("Station PIN")).toHaveValue("1234");
  fireEvent.click(screen.getByRole("button", { name: "Delete last digit" }));
  expect(screen.getByLabelText("Station PIN")).toHaveValue("123");
  fireEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(screen.getByLabelText("Station PIN")).toHaveValue("");
  rerender(<KioskPin {...props} pending />);
  expect(screen.getByRole("button", { name: "Unlocking station…" })).toBeDisabled();
  expect(screen.getByLabelText("Station PIN")).toBeDisabled();
});
