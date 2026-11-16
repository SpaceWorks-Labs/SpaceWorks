import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RelativeTime, formatRelativeTime } from "./RelativeTime";
import { expectNoA11yViolations } from "../../test/axe";

afterEach(() => vi.useRealTimers());
it("uses calendar-relative words and never emits an invalid datetime", async () => {
  const now = new Date("2026-10-15T12:00:00");
  expect(formatRelativeTime(new Date("2026-10-14T11:00:00"), now)).toBe("Yesterday");
  expect(formatRelativeTime(new Date("2026-10-24T12:00:00"), now)).toBe("In 9 days");
  expect(formatRelativeTime(new Date("2026-10-16T12:00:00"), now)).toBe("Tomorrow");
  const { container } = render(<RelativeTime date="invalid" now={now} />);
  expect(screen.getByText("Unknown time")).toBeVisible();
  expect(container.querySelector("time")).toBeNull();
  await expectNoA11yViolations(container);
});
it("refreshes each minute and removes its interval on unmount", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-15T12:00:00"));
  const { unmount } = render(<RelativeTime date="2026-10-15T11:58:00" />);
  expect(screen.getByText("2 min ago")).toBeVisible();
  act(() => vi.advanceTimersByTime(60000));
  expect(screen.getByText("3 min ago")).toBeVisible();
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});
