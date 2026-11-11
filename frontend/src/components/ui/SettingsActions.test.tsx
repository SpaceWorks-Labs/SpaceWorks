import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SettingsActions } from "./SettingsActions";
import { expectNoA11yViolations } from "../../test/axe";

it("SettingsActions renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<SettingsActions onSave={click} onDiscard={click} />);
  screen.getByRole("button",{name:"Save changes"}).focus();
  expect(screen.getByRole("button",{name:"Save changes"})).toHaveFocus();
  fireEvent.click(screen.getByRole("button",{name:"Save changes"}));
  fireEvent.click(screen.getByRole("button",{name:"Discard"}));
  expect(click).toHaveBeenCalledTimes(2);
  await expectNoA11yViolations(container);
});

it("supports form submission and blocks duplicate saves while pending", () => {
  const { rerender } = render(<SettingsActions onDiscard={() => undefined} />);
  expect(screen.getByRole("button", {name:"Save changes"})).toHaveAttribute("type", "submit");
  rerender(<SettingsActions onDiscard={() => undefined} pending />);
  expect(screen.getByRole("button", {name:"Saving…"})).toBeDisabled();
  expect(screen.getByRole("button", {name:"Discard"})).toBeDisabled();
});
