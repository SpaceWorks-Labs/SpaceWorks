import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Callout } from "./Callout";
import { expectNoA11yViolations } from "../../test/axe";

it("Callout renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<Callout size="banner" tone="warn" lead="Due tomorrow." body="Prepare the tools before handover." action={{label:"Prepare",onClick:click}} />);
  expect(screen.getByText("Due tomorrow.").tagName).toBe("STRONG");
  fireEvent.click(screen.getByRole("button",{name:"Prepare →"}));
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});

it.each(["panel", "card", "inline"] as const)("supports the %s anatomy and optional body/action", async size => {
  const { container } = render(<Callout size={size} tone="danger" lead="This removes attached items." />);
  expect(screen.getByText("This removes attached items.")).toBeVisible();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  await expectNoA11yViolations(container);
});
