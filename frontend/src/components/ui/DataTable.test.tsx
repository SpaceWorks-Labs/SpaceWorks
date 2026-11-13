import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DataTable } from "./DataTable";

describe("DataTable ordering", () => {
  const columns = [{ key: "name", header: "Name", sortable: true }];
  const data = [{ id: 1, name: "Zulu" }, { id: 2, name: "Alpha" }];

  it("preserves the server page and requests a new sort instead of reordering its rows", () => {
    const change = vi.fn();
    render(<DataTable columns={columns} data={data} ordering="name" onOrderingChange={change} />);
    expect(screen.getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Zulu", "Alpha"]);
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "ascending");
    fireEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(change).toHaveBeenCalledWith("-name");
    expect(screen.getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Zulu", "Alpha"]);
  });

  it("retains local sorting for existing unpaginated consumers", () => {
    render(<DataTable columns={columns} data={data} />);
    fireEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(screen.getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Alpha", "Zulu"]);
  });

  it("names its keyboard-scrollable region from the table caption without replacing table semantics", () => {
    render(<DataTable columns={columns} data={data} caption="Recent inventory changes" />);
    const region = screen.getByRole("region", { name: "Recent inventory changes" });
    expect(region).toHaveAttribute("tabindex", "0");
    region.focus();
    expect(region).toHaveFocus();
    expect(screen.getByRole("table", { name: "Recent inventory changes" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getAllByRole("cell")).toHaveLength(2);
  });

  it("names existing tables without a caption while keeping them keyboard scrollable", () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByRole("region", { name: "Table data" })).toHaveAttribute("tabindex", "0");
  });
});
