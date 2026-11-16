import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { Tabs } from "./Tabs";
import { expectNoA11yViolations } from "../../test/axe";

function Harness() {
  const [active, setActive] = useState("page");
  return <Tabs tabs={[{ key: "page", label: "Page", href: "/page" }, { key: "programme", label: "Programme", href: "/programme" }]}
    activeKey={active} onChange={setActive} />;
}
it("activates state tabs with arrows, wraps, and keeps one tab stop", async () => {
  const { container } = render(<Harness />);
  screen.getByRole("tab", { name: "Page" }).focus();
  fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "Programme" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Programme" })).toHaveAttribute("tabindex", "0");
  expect(screen.getByRole("tab", { name: "Page" })).toHaveAttribute("tabindex", "-1");
  fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "Page" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "End" });
  expect(screen.getByRole("tab", { name: "Programme" })).toHaveFocus();
  await expectNoA11yViolations(container);
});
