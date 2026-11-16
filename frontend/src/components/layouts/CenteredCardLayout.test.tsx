import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { LayoutGalleryExample } from "./LayoutGalleryExamples";

describe("CenteredCardLayout", () => {
  it("renders slots, one heading, one main and a focusable skip target", async () => {
    const { container } = render(<LayoutGalleryExample example="Centered card" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    await expectNoA11yViolations(container);
  });
  it("switches from loading to error with retry, then ready and empty", async () => {
    const retry = vi.fn();
    const { container, rerender } = render(<LayoutGalleryExample example="Centered card" state={{ status: "loading" }} />);
    expect(screen.getByRole("status", { name: "Loading content" })).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    rerender(<LayoutGalleryExample example="Centered card" state={{ status: "error", error: "Connection lost", onRetry: retry }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    await expectNoA11yViolations(container);
    rerender(<LayoutGalleryExample example="Centered card" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    rerender(<LayoutGalleryExample example="Centered card" isEmpty />);
    expect(screen.getByText("Nothing here yet. Add your first item.")).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container.querySelector("#main-content")).toBeInTheDocument();
  });
});
