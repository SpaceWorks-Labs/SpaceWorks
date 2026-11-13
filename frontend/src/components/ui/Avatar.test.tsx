import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Avatar } from "./Avatar";
import { expectNoA11yViolations } from "../../test/axe";

it("Avatar renders its contract and remains accessible", async () => {
  
  const { container } = render(<Avatar name="Meera Shah" seed="member-1" />);
  expect(screen.getByRole("img", {name:"Meera Shah"})).toHaveTextContent("MS");
  await expectNoA11yViolations(container);
});

it("keeps an identity's tone stable through rerenders and name changes", () => {
  const { rerender } = render(<Avatar name="Meera Shah" seed="member-1" />);
  const classes = screen.getByRole("img").className;
  rerender(<Avatar name="Meera Patel" seed="member-1" />);
  expect(screen.getByRole("img").className).toBe(classes);
  expect(screen.getByRole("img")).toHaveTextContent("MP");
});
