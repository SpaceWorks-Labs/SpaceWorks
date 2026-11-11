import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SpaceCell } from "./OverviewBlockSection";

describe("SpaceCell drill-down (#183A)", () => {
  it("links a live space to its console tab and to its reports", () => {
    render(<SpaceCell space={{ id: 7, name: "Lab", slug: "lab", excluded_reason: null, directory_hidden: false, reportsEnabled: true }} tab="bookings" />);
    expect(screen.getByRole("link", { name: "Open Lab in the console" }).getAttribute("href")).toContain("/admin/bookings?for_space=7");
    expect(screen.getByRole("link", { name: "Open Lab's reports" }).getAttribute("href")).toContain("/admin/reports?for_space=7");
  });

  it("keeps the console link when Reports is off", () => {
    render(<SpaceCell space={{ id: 7, name: "Lab", slug: "lab", excluded_reason: null, directory_hidden: false, reportsEnabled: false }} tab="bookings" />);
    expect(screen.getByRole("link", { name: "Open Lab in the console" }).getAttribute("href")).toContain("/admin/bookings?for_space=7");
    expect(screen.queryByRole("link", { name: "Open Lab's reports" })).toBeNull();
  });

  it("gives an archived space no links", () => {
    render(<SpaceCell space={{ id: 8, name: "Old", slug: "old", excluded_reason: "archived", directory_hidden: false, reportsEnabled: true }} tab="bookings" />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});
