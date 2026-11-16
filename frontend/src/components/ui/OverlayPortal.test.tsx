import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { DetailDrawer } from "./DetailDrawer";
import { Modal } from "./Modal";

it("renders dialogs at the end of the body with the page's tenant colours and kiosk sizing", () => {
  const { container } = render(<div className="sw-kiosk" style={{ "--color-brand": "1 2 3" } as React.CSSProperties}>
    <div style={{ containerType: "inline-size" }}><Modal open title="Your request" onClose={() => {}}><p>Form</p></Modal></div>
  </div>);
  const dialog = screen.getByRole("dialog", { name: "Your request" });
  expect(container.contains(dialog)).toBe(false);
  const host = dialog.parentElement!.parentElement!;
  expect(host.parentElement).toBe(document.body);
  expect(host.style.getPropertyValue("--color-brand")).toBe("1 2 3");
  expect(host).toHaveClass("sw-kiosk");
});

it("carries DetailLayout's drawer width class so its width and stacking rules still apply", () => {
  render(<div className="sw-detail-drawer sw-detail-drawer-720"><DetailDrawer open title="Request" onClose={() => {}}><p>Body</p></DetailDrawer></div>);
  const host = screen.getByRole("dialog", { name: "Request" }).parentElement!.parentElement!;
  expect(host).toHaveClass("sw-detail-drawer", "sw-detail-drawer-720");
});

it("keeps a dialog opened from inside another dialog in that dialog's layer", () => {
  const confirm = vi.fn();
  render(<Modal open title="Edit tool" onClose={() => {}}>
    <ConfirmDialog open title="Discard changes?" message="Unsaved edits are lost." onConfirm={confirm} onCancel={() => {}} />
  </Modal>);
  const outer = screen.getByRole("dialog", { name: "Edit tool" });
  expect(outer.contains(screen.getByRole("dialog", { name: "Discard changes?" }))).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(confirm).toHaveBeenCalledOnce();
});
