import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SettingsSection } from "./SettingsSection";
import { expectNoA11yViolations } from "../../test/axe";

it("SettingsSection renders its contract and remains accessible", async () => {
  
  const { container } = render(<SettingsSection title="Public details" description="Changes go live when saved."><p>Controls</p></SettingsSection>);
  expect(screen.getByRole("region",{name:"Public details"})).toBeVisible();
  await expectNoA11yViolations(container);
});
