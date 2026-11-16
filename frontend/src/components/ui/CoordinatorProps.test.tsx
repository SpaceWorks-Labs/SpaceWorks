import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { PageHeader } from "./PageHeader";
import { ConfirmDialog } from "./ConfirmDialog";
import { DangerZone } from "./DangerZone";
import { ToastHost } from "./ToastHost";
import { clearToasts, toast } from "./toastStore";
import { Tabs } from "./Tabs";

it("uses the requested heading level and retains a single full-width mobile primary", () => {
  const click = vi.fn();
  render(<PageHeader title="Tools" headingLevel={2} stickyPrimaryOnMobile primary={{ label: "Add tool", onClick: click }} />);
  expect(screen.getByRole("heading", { level: 2, name: "Tools" })).toBeVisible();
  expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  const action = screen.getByRole("button", { name: "Add tool" });
  expect(action).toHaveClass("w-full");
  expect(action.parentElement).toHaveClass("sw-sticky-primary");
  fireEvent.click(action);
  expect(click).toHaveBeenCalledOnce();
});

it("gives safe cancellation filled priority without changing either callback", () => {
  const cancel = vi.fn(), confirm = vi.fn();
  render(<ConfirmDialog open safePrimary tone="danger" title="Lock?" message="Photos will be discarded."
    cancelLabel="Keep working" confirmLabel="Discard and lock" onCancel={cancel} onConfirm={confirm} />);
  const safe = screen.getByRole("button", { name: "Keep working" });
  const danger = screen.getByRole("button", { name: "Discard and lock" });
  expect(safe).toHaveClass("desk-button-primary");
  expect(danger).toHaveClass("desk-button-danger-outline");
  fireEvent.click(safe); fireEvent.click(danger);
  expect(cancel).toHaveBeenCalledOnce(); expect(confirm).toHaveBeenCalledOnce();
});

it("does not force confirmation copy for an undoable danger action", () => {
  const click = vi.fn();
  render(<DangerZone title="Archive" consequence="You can undo this." action={{ label: "Archive", confirms: false, onClick: click }} />);
  fireEvent.click(screen.getByRole("button", { name: "Archive" }));
  expect(click).toHaveBeenCalledOnce();
});

it("supports a toast action alongside Undo", () => {
  clearToasts();
  const click = vi.fn(), undo = vi.fn(async () => {});
  render(<ToastHost />);
  act(() => { toast("Saved", { action: { label: "View", onClick: click }, undo }); });
  fireEvent.click(screen.getByRole("button", { name: "View" }));
  expect(click).toHaveBeenCalledOnce();
  expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled();
  expect(undo).not.toHaveBeenCalled();
  act(() => clearToasts());
  expect(screen.queryByRole("button", { name: "View" })).not.toBeInTheDocument();
});

it("connects controlled tabs to unique panels across tab groups", () => {
  const tabs = [{ key: "a", label: "Overview" }, { key: "b", label: "History" }];
  const change = vi.fn();
  render(<><Tabs tabs={tabs} activeKey="a" onChange={change}><p>Current content</p></Tabs>
    <Tabs tabs={tabs} activeKey="b" onChange={change}>Other content</Tabs></>);
  const selected = screen.getAllByRole("tab", { selected: true });
  expect(selected[0].id).not.toBe(selected[1].id);
  const panel = document.getElementById(selected[0].getAttribute("aria-controls")!);
  expect(panel).toHaveAttribute("role", "tabpanel");
  expect(panel).toHaveAttribute("aria-labelledby", selected[0].id);
  expect(panel).toHaveTextContent("Current content");
  selected[0].focus();
  fireEvent.keyDown(selected[0], { key: "End" });
  expect(change).toHaveBeenLastCalledWith("b");
  fireEvent.keyDown(document.activeElement!, { key: "Home" });
  expect(change).toHaveBeenLastCalledWith("a");
});
