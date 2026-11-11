import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { DetailDrawer } from "./DetailDrawer";
import { Modal } from "./Modal";

afterEach(() => vi.unstubAllGlobals());

it("opens dialogs as safe-area-aware bottom sheets on phones and centred dialogs from tablet up", () => {
  render(<Modal open title="Filters" onClose={() => {}} footer={<button>Show results</button>}><p>Fields</p></Modal>);
  const dialog = screen.getByRole("dialog", { name: "Filters" });
  expect(dialog.parentElement).toHaveClass("sw-overlay-layer", "items-end", "sm:items-center");
  expect(dialog).toHaveClass("rounded-b-none", "sm:rounded-b-xl", "max-h-full");
  expect(screen.getByRole("button", { name: "Show results" }).parentElement?.className).toContain("env(safe-area-inset-bottom)");
});

it("stacks confirm actions full width on phones with the decision on top", () => {
  render(<ConfirmDialog open title="Archive tool?" message="It leaves the catalogue." confirmLabel="Archive" onConfirm={() => {}} onCancel={() => {}} />);
  const confirm = screen.getByRole("button", { name: "Archive" });
  expect(confirm).toHaveClass("w-full", "sm:w-auto");
  expect(confirm.parentElement).toHaveClass("flex-col-reverse", "sm:flex-row");
});

it("scrolls a focused field into view once the on-screen keyboard resizes the viewport", () => {
  const listeners: (() => void)[] = [];
  vi.stubGlobal("visualViewport", { addEventListener: (_: string, listener: () => void) => listeners.push(listener), removeEventListener: vi.fn() });
  render(<DetailDrawer open title="Edit tool" onClose={() => {}}><label>Name<input /></label><button>Save</button></DetailDrawer>);
  const field = screen.getByRole("textbox", { name: "Name" });
  const scroll = vi.fn();
  field.scrollIntoView = scroll;
  fireEvent.focus(screen.getByRole("button", { name: "Save" }));
  expect(listeners).toHaveLength(0);
  fireEvent.focus(field);
  listeners.forEach(listener => listener());
  expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
  expect(screen.getByRole("heading", { name: "Edit tool" })).toHaveAttribute("title", "Edit tool");
});
