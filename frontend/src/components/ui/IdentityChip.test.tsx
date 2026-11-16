import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it } from "vitest";
import { IdentityChip } from "./IdentityChip";
import { expectNoA11yViolations } from "../../test/axe";

it("IdentityChip renders its contract and remains accessible", async () => {
  
  const { container } = render(<IdentityChip identity={{kind:"icon",icon:"Wrench",tone:"accent"}} label="Drill" />);
  expect(screen.getByRole("img", {name:"Drill"})).toBeVisible();
  await expectNoA11yViolations(container);
});

it("shows a code with Outfit tabular numerals and an accessible identity", async () => {
  const { container, rerender } = render(<IdentityChip identity={{ kind: "code", code: "BOX08" }} />);
  expect(screen.getByRole("img", { name: "BOX08" })).toHaveTextContent("BOX08");
  expect(screen.getByRole("img")).toHaveClass("font-sans", "tabular-nums");
  rerender(<IdentityChip identity={{ kind: "code", code: "BOX08" }} label="Tool box" draft />);
  expect(screen.getByRole("img", { name: "Tool box" })).toHaveTextContent("BOX08");
  await expectNoA11yViolations(container);
});

it("supports date/avatar identities and a failed image without losing its accessible name", async () => {
  const { container, rerender } = render(<IdentityChip identity={{kind:"date",date:"2026-10-14"}} />);
  expect(screen.getByText("14")).toBeVisible();
  rerender(<IdentityChip identity={{kind:"avatar",name:"Meera Shah",seed:"member-1"}} />);
  expect(screen.getByRole("img", {name:"Meera Shah"})).toHaveTextContent("MS");
  rerender(<IdentityChip label="Drill" identity={{kind:"image",src:"/missing.png"}} />);
  fireEvent.error(screen.getByRole("img"));
  expect(screen.getByRole("img", {name:"Drill"}).tagName).toBe("SPAN");
  await expectNoA11yViolations(container);
});
