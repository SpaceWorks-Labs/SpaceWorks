import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SettingsRow } from "./SettingsRow";
import { expectNoA11yViolations } from "../../test/axe";

it("SettingsRow renders its contract and remains accessible", async () => {
  
  const { container } = render(<SettingsRow label="Name" helper="Shown to members." htmlFor="space-name"><input id="space-name" /></SettingsRow>);
  expect(screen.getByRole("textbox",{name:"Name"})).toBeVisible();
  expect(screen.getByRole("group",{name:"Name"})).toBeVisible();
  await expectNoA11yViolations(container);
});
