import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { LayoutGalleryExample } from "./LayoutGalleryExamples";
import { AuthLayout } from "./AuthLayout";

describe("AuthLayout", () => {
  it("renders slots, one heading, one main and a focusable skip target", async () => {
    const { container } = render(<LayoutGalleryExample example="Auth" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    await expectNoA11yViolations(container);
  });
  it("switches from loading to error with retry, then ready and empty", async () => {
    const retry = vi.fn();
    const { container, rerender } = render(<LayoutGalleryExample example="Auth" state={{ status: "loading" }} />);
    expect(screen.getByRole("status", { name: "Loading content" })).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    rerender(<LayoutGalleryExample example="Auth" state={{ status: "error", error: "Connection lost", onRetry: retry }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    await expectNoA11yViolations(container);
    rerender(<LayoutGalleryExample example="Auth" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    rerender(<LayoutGalleryExample example="Auth" isEmpty />);
    expect(screen.getByText("Nothing here yet. Add your first item.")).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container.querySelector("#main-content")).toBeInTheDocument();
  });
  it("draws the Space Works panel as a Deep Ink island with one accent phrase, one logo and the facets", () => {
    const { container } = render(<LayoutGalleryExample example="Auth" />);
    const panel = screen.getByRole("complementary", { name: "Space Works" });
    expect(panel).toHaveClass("sw-auth-brand", "sw-island-dark", "sw-field-ink");
    expect(panel.querySelectorAll("[data-facets]")).toHaveLength(1);
    expect(panel.querySelectorAll("[data-logo]")).toHaveLength(0);
    expect(container.querySelectorAll(".font-accent")).toHaveLength(1);
    expect(panel.querySelector(".sw-auth-showcase")).toHaveAttribute("aria-hidden", "true");
  });
  it("gives a tenant its own brand field without Space Works facets", () => {
    render(<AuthLayout state={{ status: "ready" }} title="Member sign in" brand={{ tenant: { name: "Fab Lab Kochi" } }} form={<p>Form</p>} />);
    const panel = screen.getByRole("complementary", { name: "Fab Lab Kochi" });
    expect(panel).toHaveClass("sw-field-brand");
    expect(panel).not.toHaveClass("sw-island-dark");
    expect(panel.querySelector("[data-facets]")).toBeNull();
  });
});
