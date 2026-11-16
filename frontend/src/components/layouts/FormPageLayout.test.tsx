import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { LayoutGalleryExample } from "./LayoutGalleryExamples";

describe("FormPageLayout", () => {
  it("renders slots, one heading, one main and a focusable skip target", async () => {
    const { container } = render(<LayoutGalleryExample example="Form" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    await expectNoA11yViolations(container);
  });
  it("switches from loading to error with retry, then ready and empty", async () => {
    const retry = vi.fn();
    const { container, rerender } = render(<LayoutGalleryExample example="Form" state={{ status: "loading" }} />);
    expect(screen.getByRole("status", { name: "Loading content" })).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    rerender(<LayoutGalleryExample example="Form" state={{ status: "error", error: "Connection lost", onRetry: retry }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    await expectNoA11yViolations(container);
    rerender(<LayoutGalleryExample example="Form" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    rerender(<LayoutGalleryExample example="Form" isEmpty />);
    expect(screen.getByText("Nothing here yet. Add your first item.")).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container.querySelector("#main-content")).toBeInTheDocument();
  });
});

import { FormPageLayout } from "./FormPageLayout";
it("submits only after native validation, and discloses the preview on phones", () => {
  const submit = vi.fn();
  render(<FormPageLayout state={{ status: "ready" }} header={{ title: "New workshop" }} form={<input aria-label="Name" required />}
    submit={{ label: "Create", onClick: submit }} preview={{ label: "Preview", content: <input aria-label="Preview field" /> }} />);
  fireEvent.click(screen.getByRole("button", { name: "Create" })); expect(submit).not.toHaveBeenCalled();
  fireEvent.change(screen.getByRole("textbox", { name: "Name" }), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Create" })); expect(submit).toHaveBeenCalledOnce();
  expect(screen.queryByLabelText("Preview field")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Preview" }));
  expect(screen.getAllByLabelText("Preview field")).toHaveLength(1);
});
