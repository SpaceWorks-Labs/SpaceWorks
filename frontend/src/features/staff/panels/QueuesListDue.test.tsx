import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RequestList } from "./QueuesList";

vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn() }));

// A fixed morning clock: "in 2 days" is counted in calendar days, so a due time computed from the real clock
// flips to "in 3 days" late in the evening.
const NOW = new Date(2026, 5, 1, 9, 0, 0);
beforeEach(() => { vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(NOW); });
afterEach(() => { vi.useRealTimers(); });
const inTwoDays = () => new Date(NOW.getTime() + 2 * 86400000 + 3 * 3600000).toISOString();
const row = (id: number, status: string) => ({ id, status, requester_username: `user${id}`, requester_display: `User ${id}`,
  items: [], return_due_at: inTwoDays() }) as never;

function mount(rows: unknown[]) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><RequestList rows={rows as never} /></MemoryRouter></QueryClientProvider>);
}

it("shows a mid-sentence due line only while the request still holds hardware", () => {
  mount([row(1, "issued"), row(2, "returned"), row(3, "closed_with_issue")]);
  expect(screen.getAllByText(/^Due/)).toHaveLength(1);
  expect(screen.getByText("in 2 days")).toBeInTheDocument();
  expect(screen.queryByText("In 2 days")).not.toBeInTheDocument();
});
