import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ActionControl } from "./ActionControl";
import { expectNoA11yViolations } from "../../test/axe";

it("ActionControl renders its contract and remains accessible", async () => {
  
  const { container } = render(<ActionControl action={{label:"Save",disabled:true,disabledReason:"Choose an item"}} />);
  expect(screen.getByRole("button")).toBeDisabled();
  expect(screen.getByRole("button")).toHaveAccessibleDescription("Choose an item");
  await expectNoA11yViolations(container);
});

it("blocks pending links, preserves external-link safety and adds the confirmation ellipsis once", async () => {
  const click = vi.fn();
  const { container, rerender } = render(<ActionControl action={{label:"Delete",confirms:true,onClick:click}} />);
  expect(screen.getByRole("button", {name:"Delete…"})).toBeVisible();
  rerender(<ActionControl action={{label:"Delete…",confirms:true,onClick:click}} />);
  expect(screen.getByRole("button", {name:"Delete…"})).toBeVisible();
  rerender(<ActionControl action={{label:"View",href:"/view",onClick:click,pending:true,pendingLabel:"Opening…"}} />);
  const link = screen.getByRole("link", {name:"Opening…"});
  expect(link).toHaveAttribute("aria-disabled", "true");
  expect(link).not.toHaveAttribute("href");
  fireEvent.click(link);
  expect(click).not.toHaveBeenCalled();
  rerender(<ActionControl action={{label:"View",href:"/view",external:true}} />);
  expect(screen.getByRole("link")).toHaveAttribute("rel", "noopener noreferrer");
  await expectNoA11yViolations(container);
});
