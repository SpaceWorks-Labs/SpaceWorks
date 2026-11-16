import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DataTable } from "./DataTable";
import { ListRow } from "./ListRow";
import { Modal } from "./Modal";
import { OverflowMenu } from "./OverflowMenu";
import { SegmentedControl } from "./SegmentedControl";
import { Tabs } from "./Tabs";

afterEach(() => vi.restoreAllMocks());

it("scrolls the active tab into view and fades the edge where more tabs wait", () => {
  vi.spyOn(HTMLElement.prototype, "offsetLeft", "get").mockImplementation(function (this: HTMLElement) {
    return this.getAttribute("aria-selected") === "true" ? 600 : 0;
  });
  vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(() => 100);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockImplementation(() => 320);
  vi.spyOn(Element.prototype, "scrollWidth", "get").mockImplementation(() => 900);
  render(<Tabs label="Sections" activeKey="history" onChange={() => {}}
    tabs={["overview", "loans", "payments", "history"].map(key => ({ key, label: key, href: `#${key}` }))} />);
  const list = screen.getByRole("tablist", { name: "Sections" });
  expect(list.scrollLeft).toBe(600 + 100 + 24 - 320);
  fireEvent.scroll(list);
  expect(list).toHaveAttribute("data-fade", "both");
});

it("shows only interactive headers on phones and keeps the table scroll inside its own box", () => {
  render(<DataTable columns={[{ key: "name", header: "Name", sortable: true }, { key: "status", header: "Status" }]}
    data={[{ id: 1, name: "Drill", status: "Out" }]} />);
  expect(screen.getByRole("columnheader", { name: /Name/ })).toHaveClass("block", "md:table-cell");
  expect(screen.getByRole("columnheader", { name: "Status" })).toHaveClass("max-md:sr-only", "md:table-cell");
  expect(screen.getByRole("table").parentElement).toHaveClass("overflow-x-auto");
  expect(screen.getAllByRole("cell")[0]).toHaveClass("max-md:font-semibold");
});

it("leads each phone card with the title and its status, and labels only detail cells", () => {
  const { container } = render(<DataTable ordering="name" onOrderingChange={() => {}}
    columns={[{ key: "thumb", header: "", phone: "lead", render: () => <span>DR</span> }, { key: "name", header: "Item", sortable: true, phone: "title" },
      { key: "total", header: "Total" }, { key: "status", header: "Status" }, { key: "actions", header: "", render: () => <button>Issue</button> }]}
    data={[{ id: 1, name: "Drill", total: 3, status: "Available" }]} />);
  const row = screen.getAllByRole("row")[1];
  expect(row).toHaveClass("max-md:grid");
  expect(screen.getByText("Drill").closest("td")).toHaveClass("max-md:col-start-3", "max-md:row-start-1");
  expect(screen.getByText("Available").closest("td")).toHaveClass("max-md:col-start-3", "max-md:row-start-2");
  expect(screen.getByRole("button", { name: "Issue" }).closest("td")).toHaveClass("max-md:col-span-full", "max-md:border-t");
  // Only the detail cell carries a generated phone label; title and status don't repeat their headers.
  expect([...container.querySelectorAll("td [data-label]")].map(label => label.getAttribute("data-label"))).toEqual(["Total"]);
  // The page drives ordering, so the phone sort chips are hidden (the toolbar's Sort select covers it).
  expect(screen.getByRole("columnheader", { name: /Item/ })).toHaveClass("max-md:sr-only");
});

it("hides a headerless table's header row on phones", () => {
  render(<DataTable columns={[{ key: "name", header: "Name" }]} data={[{ id: 1, name: "Drill" }]} />);
  expect(screen.getAllByRole("rowgroup")[0]).toHaveClass("max-md:sr-only", "md:table-header-group");
});

it("opens an overflow menu rightwards when its trigger sits near the left edge", () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ right: 60 } as DOMRect);
  render(<OverflowMenu actions={[{ label: "Archive", onClick: () => {} }]} />);
  fireEvent.click(screen.getByRole("button", { name: "More actions" }));
  expect(screen.getByRole("menu")).toHaveClass("left-0");
});

it("opens an overflow menu leftwards from a trigger on the right", () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ right: 1200 } as DOMRect);
  render(<OverflowMenu actions={[{ label: "Archive", onClick: () => {} }]} />);
  fireEvent.click(screen.getByRole("button", { name: "More actions" }));
  expect(screen.getByRole("menu")).toHaveClass("right-0");
});

it("stretches a full-width segmented control and gives phone sheets a visible close", () => {
  render(<SegmentedControl fullWidth label="Mode" value="a" onChange={() => {}} options={[{ value: "a", label: "Borrow" }, { value: "b", label: "Return" }]} />);
  expect(screen.getByRole("radiogroup", { name: "Mode" })).toHaveClass("w-full");
  expect(screen.getByRole("radio", { name: "Borrow" })).toHaveClass("flex-1");
  const close = vi.fn();
  render(<Modal open title="Your request" onClose={close}><input aria-label="Name" /></Modal>);
  expect(screen.getByRole("textbox", { name: "Name" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
  expect(close).toHaveBeenCalledOnce();
});

it("lets a list row's actions wrap under the title instead of squeezing it", () => {
  render(<ListRow title="Laser cutter induction" href="/x" right={<button>Approve</button>} />);
  expect(screen.getByRole("link", { name: /Laser cutter/ })).toHaveClass("basis-48", "min-w-0");
});
