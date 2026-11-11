import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MinorAmountInput } from "./MinorAmountInput";

function Harness({ initial, onMinor, allowNegative }: { initial: number | null; onMinor: (minor: number | null) => void; allowNegative?: boolean }) {
  const [value, setValue] = useState<number | null>(initial);
  return <label>Amount<MinorAmountInput currency="EUR" value={value} allowNegative={allowNegative} onChange={minor => { onMinor(minor); setValue(minor); }} /></label>;
}

describe("MinorAmountInput", () => {
  it("shows stored minor units as a decimal and emits minor units for typed decimals", () => {
    const onMinor = vi.fn();
    render(<Harness initial={1250} onMinor={onMinor} />);
    const input = screen.getByLabelText("Amount");
    expect(input).toHaveValue("12.50");
    expect(input).toHaveAttribute("inputmode", "decimal");
    fireEvent.change(input, { target: { value: "7." } });
    expect(onMinor).toHaveBeenLastCalledWith(700);
    expect(input).toHaveValue("7.");
    fireEvent.change(input, { target: { value: "7.05" } });
    expect(onMinor).toHaveBeenLastCalledWith(705);
  });

  it("reports null for text that is not an amount, and for negatives unless allowed", () => {
    const onMinor = vi.fn();
    const view = render(<Harness initial={null} onMinor={onMinor} />);
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "1.234" } });
    expect(onMinor).toHaveBeenLastCalledWith(null);
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "-2" } });
    expect(onMinor).toHaveBeenLastCalledWith(null);
    view.unmount();
    render(<Harness initial={0} onMinor={onMinor} allowNegative />);
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "-2.5" } });
    expect(onMinor).toHaveBeenLastCalledWith(-250);
  });

  it("replaces the text when the parent sets a different amount", () => {
    const view = render(<label>Amount<MinorAmountInput currency="EUR" value={100} onChange={vi.fn()} /></label>);
    view.rerender(<label>Amount<MinorAmountInput currency="EUR" value={4200} onChange={vi.fn()} /></label>);
    expect(screen.getByLabelText("Amount")).toHaveValue("42.00");
  });
});
