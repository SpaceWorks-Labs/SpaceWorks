import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { expectNoA11yViolations } from "../../test/axe";
import { LayoutGalleryExample } from "./LayoutGalleryExamples";
import { DashboardLayout } from "./DashboardLayout";

describe("DashboardLayout", () => {
  it("names compact count links from their visible label and count", () => {
    render(<MemoryRouter><DashboardLayout header={{ title: "Dashboard", eyebrow: "Today" }}
      state={{ status: "ready" }} main={[]} stats={[
        { label: "First", value: 1 }, { label: "Second", value: 2 },
        { label: "Third", value: 3 }, { label: "Fourth", value: 4 },
        { label: "Problem reports", value: 0, href: "/problems" },
      ]} /></MemoryRouter>);
    const link = screen.getByRole("link", { name: "Problem reports 0" });
    expect(link).toHaveTextContent("Problem reports 0");
    expect(link).toHaveAttribute("href", "/problems");
  });
  it("renders custom rail content alone and below activity", () => {
    const props = { header: { title: "Dashboard", eyebrow: "Today" }, stats: [], main: [], state: { status: "ready" as const } };
    const { rerender } = render(<DashboardLayout {...props} railContent={<p>Backup at a glance</p>} />);
    expect(screen.getByText("Backup at a glance").closest(".sw-dashboard-rail")).toBeInTheDocument();
    rerender(<DashboardLayout {...props} rail={{ title: "Activity", items: [{ key: "a", actor: "Manager", children: "Updated a tool", date: "2026-10-14T12:00:00Z" }] }} railContent={<p>Backup at a glance</p>} />);
    const activity = screen.getByText("Updated a tool");
    const backup = screen.getByText("Backup at a glance");
    expect(activity.compareDocumentPosition(backup) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("renders slots, one heading, one main and a focusable skip target", async () => {
    const { container } = render(<LayoutGalleryExample example="Dashboard" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    await expectNoA11yViolations(container);
  });
  it("switches from loading to error with retry, then ready and empty", async () => {
    const retry = vi.fn();
    const { container, rerender } = render(<LayoutGalleryExample example="Dashboard" state={{ status: "loading" }} />);
    expect(screen.getByRole("status", { name: "Loading content" })).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    rerender(<LayoutGalleryExample example="Dashboard" state={{ status: "error", error: "Connection lost", onRetry: retry }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    await expectNoA11yViolations(container);
    rerender(<LayoutGalleryExample example="Dashboard" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    rerender(<LayoutGalleryExample example="Dashboard" isEmpty />);
    expect(screen.getByText("Nothing here yet. Add your first item.")).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container.querySelector("#main-content")).toBeInTheDocument();
  });
});
