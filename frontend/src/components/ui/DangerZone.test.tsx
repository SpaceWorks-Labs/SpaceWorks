import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DangerZone } from "./DangerZone";
import { expectNoA11yViolations } from "../../test/axe";

it("DangerZone renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<DangerZone title="Delete organisation" consequence="Permanently removes its events and memberships." action={{label:"Delete organisation",onClick:click}} />);
  const button=screen.getByRole("button",{name:"Delete organisation…"});
  expect(button).toHaveClass("desk-button-danger-outline");
  fireEvent.click(button);
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
