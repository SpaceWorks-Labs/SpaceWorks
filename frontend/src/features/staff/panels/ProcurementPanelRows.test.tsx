import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { itemTotal, labelStatus, ProcurementRow, type ToBuyItem } from "./ProcurementPanelRows";

vi.mock("./ProcurementReceipts", () => ({ ProcurementReceipts: ({ itemId, receipts, onChanged }: { itemId: number; receipts: unknown[]; onChanged: () => void }) =>
  <button type="button" onClick={onChanged}>receipts for {itemId}: {receipts.length}</button> }));

const item = (over: Partial<ToBuyItem> = {}): ToBuyItem => ({ id: 4, kind: "hardware", machine_type: null, machine_type_name: null, name: "Soldering iron", quantity: 2, link: "https://shop.test/iron",
  status: "requested", estimated_unit_cost: "50", vendor_name: "", actual_unit_cost: null, purchaser_username: null, ordered_at: null, received_at: null, moved_to_inventory_at: null,
  resulting_product: null, resulting_pool: null, resulting_machine: null, source_pool: null, created_by_username: "asha", receipts: [], ...over });

function show(row: ToBuyItem, props: Partial<Parameters<typeof ProcurementRow>[0]> = {}) {
  const handlers = { onSave: vi.fn(), onDelete: vi.fn(), onMove: vi.fn(), onReceiptsChanged: vi.fn(), onMarkBought: vi.fn() };
  render(<MemoryRouter><ProcurementRow item={row} makerspaceSlug="forge" updatePending={false} deletePending={false} {...handlers} {...props} /></MemoryRouter>);
  return handlers;
}
const menu = (name = "Soldering iron") => fireEvent.click(screen.getByRole("button", { name: `Actions for ${name}` }));

describe("row summary", () => {
  it("shows title, vendor fallback, estimate, purchaser fallback, plural receipts, and the pending status", () => {
    show(item());
    expect(screen.getByText("Soldering iron ×2")).toBeInTheDocument();
    expect(screen.getByText(/No vendor yet/)).toBeInTheDocument();
    expect(screen.getByText(/Est\. 50 each/)).toBeInTheDocument();
    expect(screen.getByText(/Unassigned purchaser/)).toBeInTheDocument();
    expect(screen.getByText(/0 receipts/)).toBeInTheDocument();
    expect(screen.getByText("Requested")).toBeInTheDocument();
  });
  it("shows the vendor, purchaser, one receipt singular, and an unknown estimate as a dash", () => {
    show(item({ vendor_name: "Hakko", purchaser_username: "ravi", estimated_unit_cost: null, receipts: [{ id: 1 } as never] }));
    expect(screen.getByText(/Hakko/)).toBeInTheDocument();
    expect(screen.getByText(/Est\. — each/)).toBeInTheDocument();
    expect(screen.getByText(/ravi/)).toBeInTheDocument();
    expect(screen.getByText(/1 receipt(?!s)/)).toBeInTheDocument();
  });
  it("flags a low-stock auto-raised row", () => {
    show(item({ source_pool: 12 }));
    expect(screen.getByText("Auto · low stock")).toBeInTheDocument();
  });
});

describe("the next-step button", () => {
  it("requested approves and approved marks ordered, saving the full draft with the new status", () => {
    const first = show(item({ vendor_name: "V", actual_unit_cost: "9" }));
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(first.onSave).toHaveBeenCalledWith({ status: "approved", vendor_name: "V", actual_unit_cost: "9" });
  });
  it("approved marks ordered", () => {
    const handlers = show(item({ status: "approved" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark ordered" }));
    expect(handlers.onSave).toHaveBeenCalledWith(expect.objectContaining({ status: "ordered" }));
  });
  it("ordered opens the drawer pre-set to Received instead of saving blind, with the receipt hint", () => {
    const handlers = show(item({ status: "ordered" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark received" }));
    expect(handlers.onSave).not.toHaveBeenCalled();
    expect(screen.getByText("Record the actual unit cost and attach the receipt, then save to mark it received.")).toBeInTheDocument();
    expect(screen.getByLabelText("Status for Soldering iron")).toHaveValue("received");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
  });
  it("shows Saving… and disables the button while an update is pending", () => {
    show(item(), { updatePending: true });
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  });
  it("received and cancelled rows have no next step; a received unmoved row offers the move", () => {
    const handlers = show(item({ status: "received" }));
    expect(screen.queryByRole("button", { name: /Approve|Mark ordered|Mark received/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Move to inventory" }));
    expect(handlers.onMove).toHaveBeenCalled();
  });
  it("a received row that came from a consumable says Refill consumable", () => {
    show(item({ status: "received", source_consumable: 7 }));
    expect(screen.getByRole("button", { name: "Refill consumable" })).toBeInTheDocument();
  });
  it("a received row already moved offers neither", () => {
    show(item({ status: "received", moved_to_inventory_at: "2026-11-01T00:00:00Z", resulting_product: 5 }));
    expect(screen.queryByRole("button", { name: /Move to inventory|Refill consumable/ })).toBeNull();
  });
});

describe("row menu", () => {
  it("offers Edit, Mark bought (when wired and there is a next step), Cancel request and Delete", () => {
    show(item());
    menu();
    expect(screen.getAllByRole("menuitem").map((entry) => entry.textContent)).toEqual(["Edit", "Mark bought", "Cancel request", "Delete…"]);
  });
  it("omits Mark bought without the handler or a next step, and Cancel once received or cancelled", () => {
    show(item({ status: "received" }), { onMarkBought: undefined });
    menu();
    expect(screen.getAllByRole("menuitem").map((entry) => entry.textContent)).toEqual(["Edit", "Delete…"]);
  });
  it("Mark bought calls the handler", () => {
    const handlers = show(item());
    menu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Mark bought" }));
    expect(handlers.onMarkBought).toHaveBeenCalled();
  });
  it("Cancel request asks first, then saves the cancelled status", () => {
    const handlers = show(item({ vendor_name: "V" }));
    menu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Cancel request" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Cancel Soldering iron?")).toBeInTheDocument();
    expect(handlers.onSave).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel request" }));
    expect(handlers.onSave).toHaveBeenCalledWith({ status: "cancelled", vendor_name: "V", actual_unit_cost: "" });
  });
  it("Delete confirms before calling onDelete", () => {
    const handlers = show(item());
    menu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete…" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Delete Soldering iron?")).toBeInTheDocument();
    expect(handlers.onDelete).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    expect(handlers.onDelete).toHaveBeenCalled();
  });
  it("cancelling the delete dialog closes it without deleting", () => {
    const handlers = show(item());
    menu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete…" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(handlers.onDelete).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("Edit opens the drawer", () => {
    show(item());
    menu();
    fireEvent.click(screen.getByRole("menuitem", { name: "Edit" }));
    expect(screen.getByLabelText("Vendor for Soldering iron")).toBeInTheDocument();
  });
});

describe("drawer", () => {
  const open = (row: ToBuyItem, props: Partial<Parameters<typeof ProcurementRow>[0]> = {}) => {
    const handlers = show(row, props);
    fireEvent.click(screen.getByText(`${row.name} ×${row.quantity}`));
    return handlers;
  };
  it("shows a safe supplier link, and edits vendor, cost and status; save is only offered once changed", () => {
    const handlers = open(item());
    expect(screen.getByRole("link", { name: "Open supplier link ↗" })).toHaveAttribute("href", "https://shop.test/iron");
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Vendor for Soldering iron"), { target: { value: "Weller" } });
    fireEvent.change(screen.getByLabelText("Actual unit cost for Soldering iron"), { target: { value: "45.5" } });
    fireEvent.change(screen.getByLabelText("Status for Soldering iron"), { target: { value: "ordered" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(handlers.onSave).toHaveBeenCalledWith({ status: "ordered", vendor_name: "Weller", actual_unit_cost: "45.5" });
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.getByLabelText("Vendor for Soldering iron")).toHaveValue("");
  });
  it("shows an unsafe link as plain text, and a dash when there is none", () => {
    const { unmount } = render(<MemoryRouter><ProcurementRow item={item({ link: "javascript:alert(1)" })} makerspaceSlug="forge" updatePending={false} deletePending={false} onSave={vi.fn()} onDelete={vi.fn()} onMove={vi.fn()} onReceiptsChanged={vi.fn()} /></MemoryRouter>);
    fireEvent.click(screen.getByText("Soldering iron ×2"));
    expect(screen.queryByRole("link", { name: "Open supplier link ↗" })).toBeNull();
    expect(screen.getByTitle("javascript:alert(1)")).toBeInTheDocument();
    unmount();
    open(item({ link: "" }));
    expect(screen.queryByRole("link", { name: "Open supplier link ↗" })).toBeNull();
  });
  it("shows ordered and received times and the purchaser", () => {
    open(item({ status: "received", purchaser_username: "ravi", ordered_at: "2026-11-01T00:00:00Z", received_at: "2026-11-02T00:00:00Z" }));
    expect(screen.getByText(/^Ordered/, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/Received/, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/Purchaser:/)).toHaveTextContent("ravi");
  });
  it.each([
    [{ resulting_product: 5 }, /Inventory #5/],
    [{ resulting_pool: 6 }, /Pool #6/],
    [{ resulting_machine: 7 }, /Machine #7/],
    [{}, /Moved/],
  ] as Array<[Partial<ToBuyItem>, RegExp]>)("where a moved row went: %j", (extra, pattern) => {
    open(item({ status: "received", moved_to_inventory_at: "2026-11-03T00:00:00Z", ...extra }));
    expect(screen.getByText(pattern)).toBeInTheDocument();
  });
  it("links the inventory product for the space", () => {
    open(item({ status: "received", moved_to_inventory_at: "2026-11-03T00:00:00Z", resulting_product: 5 }));
    expect(screen.getByRole("link", { name: "Inventory #5" })).toHaveAttribute("href", "/m/forge/admin/inventory?item=5");
  });
  it("hands receipts through and reports changes", () => {
    const handlers = open(item({ receipts: [{ id: 1 } as never] }));
    fireEvent.click(screen.getByRole("button", { name: "receipts for 4: 1" }));
    expect(handlers.onReceiptsChanged).toHaveBeenCalled();
  });
  it("shows the update error inside the open drawer, and the delete error beside the row", () => {
    open(item(), { updateError: "Cost must be positive", deleteError: "Cannot delete a bought item" });
    expect(screen.getAllByText("Cost must be positive").length).toBeGreaterThan(0);
    expect(screen.getByText("Cannot delete a bought item")).toBeInTheDocument();
  });
  it("shows the update error beside the row while the drawer is closed", () => {
    show(item(), { updateError: "Could not save" });
    expect(screen.getByText("Could not save")).toBeInTheDocument();
  });
});

describe("helpers", () => {
  it("labelStatus capitalises and replaces underscores", () => {
    expect(labelStatus("requested")).toBe("Requested");
    expect(labelStatus("cancelled")).toBe("Cancelled");
  });
  it("itemTotal multiplies the estimate by quantity, preferring the actual cost in actual mode", () => {
    expect(itemTotal(item({ quantity: 3, estimated_unit_cost: "10" }), "estimated")).toBe(30);
    expect(itemTotal(item({ quantity: 3, estimated_unit_cost: "10", actual_unit_cost: "12" }), "actual")).toBe(36);
    expect(itemTotal(item({ quantity: 3, estimated_unit_cost: "10", actual_unit_cost: null }), "actual")).toBe(30);
    expect(itemTotal(item({ estimated_unit_cost: null }), "estimated")).toBe(0);
    expect(itemTotal(item({ estimated_unit_cost: "abc" }), "estimated")).toBe(0);
  });
});
