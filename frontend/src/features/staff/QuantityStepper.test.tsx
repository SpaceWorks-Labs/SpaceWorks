import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { QuantityStepper } from "./QuantityStepper";

function Harness({ initial = "1", min, max }: { initial?: string; min?: number; max?: number }) {
  const [value, setValue] = useState(initial);
  return <label>Returned<QuantityStepper label="returned" min={min} max={max} value={value} onValueChange={setValue} /></label>;
}

const decrease = (container: HTMLElement) => container.querySelector<HTMLButtonElement>('button[title="Decrease returned"]')!;
const increase = (container: HTMLElement) => container.querySelector<HTMLButtonElement>('button[title="Increase returned"]')!;

describe("QuantityStepper", () => {
  it("keeps the wrapping label naming the number field, with a numeric phone keypad", () => {
    render(<Harness />);
    const input = screen.getByLabelText("Returned");
    expect(input).toHaveAttribute("type", "number");
    expect(input).toHaveAttribute("inputmode", "numeric");
    // The − / + buttons are touch affordances only: hidden from AT and the tab order.
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("gives the − and + buttons a 44px touch target", () => {
    const { container } = render(<Harness />);
    for (const button of [decrease(container), increase(container)]) {
      expect(button.className).toMatch(/\bw-11\b/);
      expect(button.className).toMatch(/\bdesk-button\b/);
      expect(button).toHaveAttribute("tabindex", "-1");
    }
  });

  it("nudges within min and max and disables a button at its bound", () => {
    const { container } = render(<Harness initial="1" min={0} max={2} />);
    const input = screen.getByLabelText("Returned") as HTMLInputElement;
    fireEvent.click(increase(container));
    expect(input.value).toBe("2");
    expect(increase(container)).toBeDisabled();
    fireEvent.click(decrease(container));
    fireEvent.click(decrease(container));
    expect(input.value).toBe("0");
    expect(decrease(container)).toBeDisabled();
  });

  it("starts an empty field at the first unit and still accepts typed values", () => {
    const { container } = render(<Harness initial="" min={0} />);
    const input = screen.getByLabelText("Returned") as HTMLInputElement;
    fireEvent.click(increase(container));
    expect(input.value).toBe("1");
    fireEvent.change(input, { target: { value: "7" } });
    expect(input.value).toBe("7");
  });
});
