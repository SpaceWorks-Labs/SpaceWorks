import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Field } from "./Field";
import { expectNoA11yViolations } from "../../test/axe";

it("Field renders its contract and remains accessible", async () => {
  
  const { container } = render(<Field label="Name" hint="Public name." error="Enter a name."><input /></Field>);
  const input=screen.getByRole("textbox",{name:"Name"});
  expect(input).toHaveAttribute("aria-invalid","true");
  expect(input).toHaveAccessibleDescription("Public name. Enter a name.");
  await expectNoA11yViolations(container);
});
