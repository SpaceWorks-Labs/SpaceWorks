import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { ResultPanel } from "./ResultPanel";
it.each(["success", "warn", "danger"] as const)("announces a %s result with text, Next and optional Undo", async tone => {
  const next = vi.fn(), undo = vi.fn();
  const { container } = render(<ResultPanel tone={tone} title="Tool found" summary="Drill · BOX-0042"
    next={{ label: "Next", onClick: next }} undo={{ label: "Undo", onClick: undo }} />);
  expect(screen.getByRole(tone === "danger" ? "alert" : "status")).toHaveTextContent("Tool found");
  fireEvent.click(screen.getByRole("button", { name: "Next" })); expect(next).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "Undo" })); expect(undo).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});
