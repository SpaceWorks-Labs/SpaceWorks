import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { DataTable } from "./DataTable";
import { useUrlListState } from "../../lib/useUrlListState";
import { expectNoA11yViolations } from "../../test/axe";

const columns = [{ key: "name", header: "Name", sortable: true }];
it("preserves off-page ids when selecting or clearing the visible page", async () => {
  const change = vi.fn();
  const { container, rerender } = render(<DataTable columns={columns}
    data={[{ id: 2, name: "Drill" }, { id: 3, name: "Saw" }]} selectedIds={[1, 2]} onSelectionChange={change} />);
  expect(screen.getByRole("checkbox", { name: "Select all rows" })).toBePartiallyChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: "Select all rows" }));
  expect(change).toHaveBeenLastCalledWith([1, 2, 3]);
  rerender(<DataTable columns={columns} data={[{ id: 2, name: "Drill" }, { id: 3, name: "Saw" }]}
    selectedIds={[1, 2, 3]} onSelectionChange={change} />);
  fireEvent.click(screen.getByRole("checkbox", { name: "Select all rows" }));
  expect(change).toHaveBeenLastCalledWith([1]);
  expect(screen.getAllByRole("cell")).toHaveLength(4);
  expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  const table = screen.getByRole("table");
  expect(table).not.toHaveClass("min-w-[640px]");
  expect(table).toHaveClass("md:min-w-[640px]");
  // The first column is each phone card's title, so it carries no repeated header label.
  expect(container.querySelectorAll('[data-label="Name"]')).toHaveLength(0);
  await expectNoA11yViolations(container);
});
function PresentationTable() {
  const list = useUrlListState({ page: "1" });
  return <DataTable listState={list} columns={[{ key: "name", header: "Name" }, { key: "actions", header: "", render: () => <button>View</button> }]}
    data={[{ id: 1, name: "Drill" }]} />;
}
it("names headerless column pickers and removes hidden columns from the one DOM", async () => {
  const { container } = render(<MemoryRouter><PresentationTable /></MemoryRouter>);
  fireEvent.click(screen.getByText("Columns"));
  const picker = screen.getByRole("checkbox", { name: "actions" });
  expect(picker).toBeChecked();
  fireEvent.click(picker);
  expect(screen.queryByRole("button", { name: "View" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("cell")).toHaveLength(1);
  await expectNoA11yViolations(container);
});
it("renders the same loading and empty contracts without duplicating cells", async () => {
  const { container, rerender } = render(<DataTable columns={columns} data={[]} loading skeletonCols={1} />);
  expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");
  expect(screen.getAllByRole("cell")).toHaveLength(6);
  await expectNoA11yViolations(container);
  rerender(<DataTable columns={columns} data={[]} emptyTitle="No tools yet." emptyDescription="Add your first tool above." />);
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "No tools yet." })).toBeVisible();
  expect(screen.getByText("Add your first tool above.")).toBeVisible();
  await expectNoA11yViolations(container);
});
