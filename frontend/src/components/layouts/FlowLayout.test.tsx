import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { LayoutGalleryExample } from "./LayoutGalleryExamples";

describe("FlowLayout", () => {
  it("renders slots, one heading, one main and a focusable skip target", async () => {
    const { container } = render(<LayoutGalleryExample example="Flow" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    await expectNoA11yViolations(container);
  });
  it("switches from loading to error with retry, then ready and empty", async () => {
    const retry = vi.fn();
    const { container, rerender } = render(<LayoutGalleryExample example="Flow" state={{ status: "loading" }} />);
    expect(screen.getByRole("status", { name: "Loading content" })).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    rerender(<LayoutGalleryExample example="Flow" state={{ status: "error", error: "Connection lost", onRetry: retry }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    await expectNoA11yViolations(container);
    rerender(<LayoutGalleryExample example="Flow" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    rerender(<LayoutGalleryExample example="Flow" isEmpty />);
    expect(screen.getByText("Nothing here yet. Add your first item.")).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container.querySelector("#main-content")).toBeInTheDocument();
  });
});

import { FlowLayout } from "./FlowLayout";

it("only completed steps are selectable, supports arrow/Home/End focus, and focuses changed work", () => {
  vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  const select = vi.fn();
  const props = { state: { status: "ready" } as const, title: "Issue", current: "photo", onStepSelect: select,
    steps: [{ key: "tool", label: "Tool", state: "done" as const }, { key: "box", label: "Box", state: "done" as const },
      { key: "photo", label: "Photo", state: "current" as const }, { key: "confirm", label: "Confirm", state: "todo" as const }],
    work: <input aria-label="Remarks" />, footer: { next: { label: "Next", onClick: vi.fn() } }, onCancel: vi.fn() };
  const { rerender } = render(<FlowLayout {...props} />);
  const tool = screen.getByRole("button", { name: "Tool" }), box = screen.getByRole("button", { name: "Box" });
  expect(tool.tagName).toBe("BUTTON");
  expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
  tool.focus(); fireEvent.keyDown(tool, { key: "ArrowDown" }); expect(box).toHaveFocus();
  fireEvent.keyDown(box, { key: "Home" }); expect(tool).toHaveFocus();
  fireEvent.keyDown(tool, { key: "End" }); expect(box).toHaveFocus();
  fireEvent.click(box); expect(select).toHaveBeenCalledWith("box");
  rerender(<FlowLayout {...props} current="box" />);
  expect(screen.getByLabelText("Box")).toHaveFocus();
  vi.unstubAllGlobals();
});
it("guards dialog Escape and cancellation, and hides a single step", async () => {
  const cancel = vi.fn();
  const { container } = render(<FlowLayout state={{ status: "ready" }} title="New transfer" presentation="dialog" open
    steps={[{ key: "items", label: "Items", state: "current" }]} current="items" work={<p>Transfer form</p>}
    footer={{ next: { label: "Create transfer", disabled: true, disabledReason: "Choose an item first." } }} onCancel={cancel}
    leaveGuard="Your selected items will be left unfinished." />);
  expect(screen.queryByRole("navigation", { name: "Flow steps" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create transfer" })).toBeDisabled();
  expect(screen.getByText("Choose an item first.", { selector: "p" })).toBeVisible();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(cancel).not.toHaveBeenCalled();
  expect(screen.getByRole("dialog", { name: "Leave this task?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Keep working" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Leave task" }));
  expect(cancel).toHaveBeenCalledOnce();
  await expectNoA11yViolations(container);
});

it("blocks Cancel and dialog Escape while the current action is pending", () => {
  const cancel = vi.fn();
  render(<FlowLayout state={{ status: "ready" }} title="Save" presentation="dialog" open standalone
    steps={[]} current="save" work={<p>Saving work</p>} onCancel={cancel}
    footer={{ next: { label: "Save", pending: true } }} />);
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  expect(screen.queryByRole("main")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(cancel).not.toHaveBeenCalled();
});

it("composes a kiosk work panel with an h2, large targets and live errors", async () => {
  const { container } = render(<FlowLayout state={{ status: "ready" }} title="Issue hardware" presentation="kiosk" standalone pending
    subject="Review the photo" steps={[]} current="issue" work={<p>Photo captured</p>} onCancel={vi.fn()}
    footer={{ next: { label: "Issue" } }} error={{ size: "inline", tone: "danger", lead: "Try the upload again." }} />);
  expect(screen.getByRole("heading", { level: 2, name: "Issue hardware" })).toBeVisible();
  expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  expect(screen.queryByRole("main")).not.toBeInTheDocument();
  expect(container.querySelector("#main-content")).toBeNull();
  expect(container.querySelector(".sw-kiosk-flow")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("Try the upload again.");
  await expectNoA11yViolations(container);
});
