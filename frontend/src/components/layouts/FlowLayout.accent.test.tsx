import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { FlowLayout, type FlowLayoutProps } from "./FlowLayout";

const base: FlowLayoutProps = {
  title: "Link your staff account", subject: "Bring a second account's roles into this one.",
  steps: [{ key: "start", label: "Start", state: "current" }, { key: "confirm", label: "Confirm", state: "todo" }],
  current: "start", work: <p>Work</p>, footer: { next: { label: "Continue", onClick: () => {} } }, onCancel: () => {},
  state: { status: "ready" },
};

describe("FlowLayout accentTitle", () => {
  it("sets the title in the Unbounded accent, once, when asked", async () => {
    const { container } = render(<FlowLayout {...base} accentTitle />);
    const heading = screen.getByRole("heading", { level: 1, name: "Link your staff account" });
    expect(heading).toHaveClass("font-accent", "title-page");
    expect(container.querySelectorAll(".font-accent")).toHaveLength(1);
    await expectNoA11yViolations(container);
  });

  it("keeps the plain display-face title by default", () => {
    const { container } = render(<FlowLayout {...base} />);
    expect(screen.getByRole("heading", { level: 1 })).not.toHaveClass("font-accent");
    expect(container.querySelector(".font-accent")).toBeNull();
  });

  it("carries the accent into the dialog and kiosk presentations", () => {
    const { unmount } = render(<FlowLayout {...base} presentation="dialog" open accentTitle />);
    expect(screen.getAllByRole("heading", { name: "Link your staff account" }).some(node => node.classList.contains("font-accent"))).toBe(true);
    unmount();
    render(<FlowLayout {...base} presentation="kiosk" accentTitle />);
    expect(screen.getByRole("heading", { level: 2, name: "Link your staff account" })).toHaveClass("font-accent");
  });
});
