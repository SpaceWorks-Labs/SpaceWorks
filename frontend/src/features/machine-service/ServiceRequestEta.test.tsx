import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { clockLabel, minutesLabel, ServiceRequestEta } from "./ServiceRequestEta";
import type { ServiceRequestEta as Eta } from "./types";
import { statusRefetchInterval } from "./types";

const now = new Date("2026-10-18T10:00:00Z");
function eta(overrides: Partial<Eta> = {}): Eta {
  return {
    calculated_at: "2026-10-18T10:00:00Z", estimated_start_at: "2026-10-18T10:50:00Z",
    estimated_finish_at: "2026-10-18T11:05:00Z", start_in_minutes: 50, finish_in_minutes: 65,
    confidence: "estimated", reasons: [], approved_ahead: 2, awaiting_review_ahead: 0,
    active_machine_count: 2, missing_estimate_count: 0, ...overrides,
  };
}

describe("ServiceRequestEta", () => {
  it("shows the server start and finish as an estimate with machine-readable times", async () => {
    const { container } = render(<ServiceRequestEta eta={eta()} status="accepted" now={now} />);
    expect(screen.getByText(/Starts in about 50 min/)).toBeInTheDocument();
    const times = container.querySelectorAll("time");
    expect([...times].map(time => time.getAttribute("dateTime"))).toContain("2026-10-18T11:05:00Z");
    expect(screen.getByText("2 approved jobs ahead of you")).toBeInTheDocument();
    expect(screen.getByText(/continuous machine time and depend on staff availability/)).toBeInTheDocument();
    expect(container.querySelector("[aria-live]")).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("only an approved first-in-line job is next; a pending one is awaiting review", () => {
    const { rerender } = render(<ServiceRequestEta eta={eta({ approved_ahead: 0 })} status="accepted" now={now} />);
    expect(screen.getByText("You're next among approved jobs")).toBeInTheDocument();
    rerender(<ServiceRequestEta eta={eta({ approved_ahead: 0, confidence: "rough", reasons: ["awaiting_approval"] })} status="pending" now={now} />);
    expect(screen.getByText("Awaiting review")).toBeInTheDocument();
    expect(screen.getByText("If approved")).toBeInTheDocument();
    expect(screen.queryByText("You're next among approved jobs")).toBeNull();
  });

  it("is honest when the estimate is unavailable or rough", () => {
    const { rerender } = render(<ServiceRequestEta eta={eta({ confidence: "unavailable", estimated_start_at: null, estimated_finish_at: null,
      start_in_minutes: null, finish_in_minutes: null, reasons: ["missing_estimate"] })} status="accepted" now={now} />);
    expect(screen.getByText("Estimate unavailable")).toBeInTheDocument();
    expect(screen.getByText(/has no time estimate yet/)).toBeInTheDocument();
    expect(screen.queryByText(/Starts in/)).toBeNull();
    rerender(<ServiceRequestEta eta={eta({ confidence: "rough", reasons: ["overdue_running_job"] })} status="accepted" now={now} />);
    expect(screen.getByText("Rough estimate")).toBeInTheDocument();
    expect(screen.getByText(/taking longer than estimated/)).toBeInTheDocument();
  });

  it("running jobs show only their finish; terminal jobs render nothing", () => {
    const { container, rerender } = render(<ServiceRequestEta eta={eta({ start_in_minutes: 0 })} status="printing" now={now} />);
    expect(screen.getByText(/Done around/)).toBeInTheDocument();
    expect(screen.queryByText(/Starts in/)).toBeNull();
    rerender(<ServiceRequestEta eta={null} status="cancelled" now={now} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("labels minutes and adds the date once the time is not today", () => {
    expect([minutesLabel(0), minutesLabel(5), minutesLabel(65), minutesLabel(120)]).toEqual(["now", "about 5 min", "about 1 h 5 min", "about 2 h"]);
    const tomorrow = new Date(now.getTime() + 26 * 3_600_000).toISOString();
    expect(clockLabel(tomorrow, now).length).toBeGreaterThan(clockLabel(now.toISOString(), now).length);
  });

  it("stops polling once a job is terminal, including cancelled", () => {
    expect(statusRefetchInterval("printing")).toBe(30_000);
    expect(statusRefetchInterval("accepted")).toBe(90_000);
    for (const status of ["completed", "collected", "failed", "rejected", "cancelled", undefined]) {
      expect(statusRefetchInterval(status)).toBe(false);
    }
  });
});
