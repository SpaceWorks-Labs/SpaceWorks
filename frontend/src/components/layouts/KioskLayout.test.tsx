import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { LayoutGalleryExample } from "./LayoutGalleryExamples";

describe("KioskLayout", () => {
  it("renders slots, one heading, one main and a focusable skip target", async () => {
    const { container } = render(<LayoutGalleryExample example="Kiosk" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    await expectNoA11yViolations(container);
  });
  it("switches from loading to error with retry, then ready and empty", async () => {
    const retry = vi.fn();
    const { container, rerender } = render(<LayoutGalleryExample example="Kiosk" state={{ status: "loading" }} />);
    expect(screen.getByRole("status", { name: "Loading content" })).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    rerender(<LayoutGalleryExample example="Kiosk" state={{ status: "error", error: "Connection lost", onRetry: retry }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    await expectNoA11yViolations(container);
    rerender(<LayoutGalleryExample example="Kiosk" />);
    expect(screen.getByText("Sample content")).toBeInTheDocument();
    rerender(<LayoutGalleryExample example="Kiosk" isEmpty />);
    expect(screen.getByText("Nothing here yet. Add your first item.")).toBeInTheDocument();
    expect(screen.queryByText("Sample content")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container.querySelector("#main-content")).toBeInTheDocument();
  });
});

import { KioskLayout } from "./KioskLayout";
it("announces offline queued work and supports the PIN keypad", async () => {
  const unlock = vi.fn();
  const { container } = render(<KioskLayout state={{ status: "ready" }} context={{ title: "Station", subtitle: "Door" }}
    connection={{ online: false, queued: 2 }} headerActions={[{ label: "Lock station", onClick: vi.fn() }]} mode="lock"
    lock={{ title: "Enter PIN", helper: "Ask staff for the PIN.", pinLength: 4, pending: false, onSubmit: unlock }}
    work={{ capture: <p>Capture waits for unlock.</p>, panel: <p role="status">Local queue storage unavailable.</p> }} />);
  expect(screen.getByText("Offline · 2 queued")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Local queue storage unavailable.");
  expect(screen.queryByText("Capture waits for unlock.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open station" })).toBeDisabled();
  for (const key of ["1", "2", "3", "4"]) fireEvent.click(screen.getByRole("button", { name: key }));
  fireEvent.click(screen.getByRole("button", { name: "Open station" }));
  expect(unlock).toHaveBeenCalledWith("1234");
  await expectNoA11yViolations(container);
});

it("uses a station-specific lock consequence and keeps the safe action primary", () => {
  const discard = vi.fn(), keep = vi.fn();
  render(<KioskLayout state={{ status: "ready" }} context={{ title: "Door", subtitle: "Event" }}
    connection={{ online: false }} headerActions={[]} mode="work"
    confirmLock={{ title: "Discard check-ins?", consequence: "Two check-ins have not reached the server.", onDiscard: discard, onKeep: keep }} />);
  expect(screen.getByRole("dialog", { name: "Discard check-ins?" })).toBeVisible();
  expect(screen.getByText("Two check-ins have not reached the server.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Keep working" })).toHaveClass("desk-button-primary");
  expect(screen.getByRole("button", { name: "Discard and lock" })).toHaveClass("desk-button-danger-outline");
  fireEvent.click(screen.getByRole("button", { name: "Keep working" }));
  expect(keep).toHaveBeenCalledOnce();
  expect(discard).not.toHaveBeenCalled();
});
