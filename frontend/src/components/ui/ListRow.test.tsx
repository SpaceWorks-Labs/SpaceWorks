import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ListRow } from "./ListRow";
import { expectNoA11yViolations } from "../../test/axe";

it("ListRow renders its contract and remains accessible", async () => {
  const click=vi.fn();
  const { container } = render(<ListRow title="Demo Summit" meta="Tomorrow · Public" draft href="/events/1" identity={{kind:"date",date:"2026-10-14"}} right={<button onClick={click}>Publish</button>} />);
  expect(screen.getByRole("link")).toHaveAttribute("href","/events/1");
  expect(screen.getByRole("link").querySelector("button")).toBeNull();
  fireEvent.click(screen.getByRole("button"));
  expect(click).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
