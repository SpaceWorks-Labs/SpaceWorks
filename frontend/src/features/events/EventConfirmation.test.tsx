import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { countdownText, EventCountdown } from "./EventCountdown";
import { googleCalendarUrl } from "./eventConfirmation";

describe("public event countdown", () => {
  it("updates to happening now and ended as the clock advances", () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-20T10:00:00Z"));
    try {
      render(<EventCountdown startsAt="2026-10-20T10:01:00Z" endsAt="2026-10-20T10:02:00Z" />);
      expect(screen.getByText("Starts in 1m")).toBeVisible();
      act(() => vi.advanceTimersByTime(60_000)); expect(screen.getByText("Happening now")).toBeVisible();
      act(() => vi.advanceTimersByTime(60_000)); expect(screen.getByText("Event ended")).toBeVisible();
    } finally { vi.useRealTimers(); }
  });
  it("formats days and avoids invalid date countdowns", () => {
    expect(countdownText("2026-10-22T11:00:00Z", "2026-10-22T12:00:00Z", Date.parse("2026-10-20T10:00:00Z"))).toBe("Starts in 2d 1h");
    expect(countdownText("invalid", "invalid", Date.now())).toBe("");
  });
});

it("formats Google Calendar from only the public event fields", () => {
  const url = new URL(googleCalendarUrl({ title: "Workshop & talk", description: "Public description", starts_at: "2026-10-20T10:00:00+05:30", ends_at: "2026-10-20T12:00:00+05:30", location: "Main hall" }));
  expect(url.origin).toBe("https://calendar.google.com");
  expect(url.searchParams.get("dates")).toBe("20261020T043000Z/20261020T063000Z");
  expect([...url.searchParams.keys()]).toEqual(["action", "text", "dates", "details", "location"]);
  expect(url.searchParams.get("text")).toBe("Workshop & talk");
});
